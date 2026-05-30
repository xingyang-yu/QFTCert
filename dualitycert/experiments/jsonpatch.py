"""Minimal RFC-6902 JSON Patch applier (add / remove / replace).

The repair loop lets the model emit a list of patch operations against a
theory JSON. We implement only the three operations the repair schema
allows (add / remove / replace) over JSON-pointer paths like
``/superpotential/0/coefficient`` or ``/arrows/2/r_charge``. Anything
malformed returns an error string rather than raising, so the repair
loop can record a schema-invalid round and move on.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence


__all__ = ["JsonPatchError", "apply_patches"]


class JsonPatchError(ValueError):
    """A patch operation could not be applied."""


def apply_patches(
    document: Any, patches: Sequence[dict]
) -> tuple[Any, str | None]:
    """Apply `patches` to a deep copy of `document`.

    Returns `(new_document, None)` on success or `(original, error)` on
    the first failed operation (the original is returned unmodified).
    """

    try:
        doc = deepcopy(document)
        for i, patch in enumerate(patches):
            doc = _apply_one(doc, patch, i)
        return doc, None
    except JsonPatchError as exc:
        return document, str(exc)


def _apply_one(doc: Any, patch: dict, index: int) -> Any:
    if not isinstance(patch, dict):
        raise JsonPatchError(f"patch[{index}] is not an object: {patch!r}")
    op = patch.get("op")
    path = patch.get("path")
    if op not in {"add", "remove", "replace"}:
        raise JsonPatchError(f"patch[{index}] has unsupported op {op!r}")
    if not isinstance(path, str):
        raise JsonPatchError(f"patch[{index}] path must be a string: {path!r}")
    tokens = _parse_pointer(path)
    if op in {"add", "replace"} and "value" not in patch:
        raise JsonPatchError(f"patch[{index}] op {op!r} requires a 'value'")
    value = patch.get("value")

    if not tokens:
        if op in {"add", "replace"}:
            return deepcopy(value)
        raise JsonPatchError("cannot remove the whole document")

    parent = _resolve(doc, tokens[:-1], index)
    last = tokens[-1]

    if isinstance(parent, list):
        return _apply_list(doc, parent, last, op, value, index)
    if isinstance(parent, dict):
        return _apply_dict(doc, parent, last, op, value, index)
    raise JsonPatchError(
        f"patch[{index}] parent at {'/'.join(tokens[:-1])!r} is not a "
        f"container: {type(parent).__name__}"
    )


def _apply_list(doc, parent, token, op, value, index):
    if op == "add":
        if token == "-":
            parent.append(deepcopy(value))
            return doc
        idx = _list_index(token, len(parent), index, allow_end=True)
        parent.insert(idx, deepcopy(value))
        return doc
    idx = _list_index(token, len(parent), index, allow_end=False)
    if op == "remove":
        parent.pop(idx)
    else:  # replace
        parent[idx] = deepcopy(value)
    return doc


def _apply_dict(doc, parent, token, op, value, index):
    if op == "remove":
        if token not in parent:
            raise JsonPatchError(
                f"patch[{index}] remove: key {token!r} not present"
            )
        del parent[token]
    elif op == "replace":
        if token not in parent:
            raise JsonPatchError(
                f"patch[{index}] replace: key {token!r} not present"
            )
        parent[token] = deepcopy(value)
    else:  # add (create or overwrite)
        parent[token] = deepcopy(value)
    return doc


def _resolve(doc: Any, tokens: Sequence[str], index: int) -> Any:
    node = doc
    for depth, token in enumerate(tokens):
        if isinstance(node, list):
            idx = _list_index(token, len(node), index, allow_end=False)
            node = node[idx]
        elif isinstance(node, dict):
            if token not in node:
                raise JsonPatchError(
                    f"patch[{index}] path segment {token!r} not found"
                )
            node = node[token]
        else:
            raise JsonPatchError(
                f"patch[{index}] cannot descend into {type(node).__name__} "
                f"at segment {token!r}"
            )
    return node


def _list_index(token: str, length: int, index: int, *, allow_end: bool) -> int:
    try:
        idx = int(token)
    except (TypeError, ValueError):
        raise JsonPatchError(
            f"patch[{index}] array index {token!r} is not an integer"
        )
    upper = length if allow_end else length - 1
    if idx < 0 or idx > upper:
        raise JsonPatchError(
            f"patch[{index}] array index {idx} out of range [0, {upper}]"
        )
    return idx


def _parse_pointer(pointer: str) -> list[str]:
    """Parse an RFC-6901 JSON pointer into its decoded tokens."""

    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise JsonPatchError(f"JSON pointer must start with '/': {pointer!r}")
    return [
        seg.replace("~1", "/").replace("~0", "~")
        for seg in pointer.split("/")[1:]
    ]
