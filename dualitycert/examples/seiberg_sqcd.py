"""Run the first SQCD-like Seiberg duality certificate example."""

from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim


def main() -> None:
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    certificate = evaluate_claim(claim)
    print(certificate.render_text())


if __name__ == "__main__":
    main()
