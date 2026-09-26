"""Command line interface.

Esempi:
    python -m atlas3d parametri
    python -m atlas3d tavola cute --viste laterale --campioni 256
    python -m atlas3d tavola vascolare --preset male --set dorsal_nasal_pattern=single_dominant
    python -m atlas3d atlante --uscita atlante/ --risoluzione 2400
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .params import ParameterError, PRESETS, load_params, parse_overrides


def _common(sp):
    sp.add_argument("--parametri", help="file YAML dei parametri (default: params/naso_adulto.yaml)")
    sp.add_argument("--preset", default="female", choices=sorted(PRESETS))
    sp.add_argument("--set", dest="overrides", action="append", default=[], metavar="CHIAVE=VALORE",
                    help="sovrascrive un parametro, es. --set nasolabial_angle=108")


def _render_args(sp):
    sp.add_argument("--uscita", default="output", type=Path)
    sp.add_argument("--risoluzione", type=int, default=1800, help="larghezza del render in pixel")
    sp.add_argument("--campioni", type=int, default=192, help="campioni Cycles per pixel")
    sp.add_argument("--voxel", type=float, default=0.3, help="passo della griglia SDF in mm")
    sp.add_argument("--lingua", default="it", choices=["it", "en"])
    sp.add_argument("--sfondo", default="dark", choices=["dark", "light"])
    sp.add_argument("--senza-etichette", action="store_true")
    sp.add_argument("--glb", action="store_true", help="esporta anche la scena in glTF binario")
    sp.add_argument("--dispositivo", default="cpu", choices=["cpu", "gpu"],
                    help="gpu usa OptiX/CUDA/HIP/Metal se disponibili")
    sp.add_argument("--filler", action="store_true", help="aggiunge un bolo di filler")
    sp.add_argument("--filler-volume", type=float, help="ml")
    sp.add_argument("--filler-sede", type=float, help="frazione del dorso (0 = radix)")


def _load(args):
    ov = parse_overrides(args.overrides)
    if getattr(args, "filler", False):
        ov["filler.enabled"] = "true"
    if getattr(args, "filler_volume", None) is not None:
        ov["filler.volume"] = args.filler_volume
    if getattr(args, "filler_sede", None) is not None:
        ov["filler.site"] = args.filler_sede
    return load_params(args.parametri, preset=args.preset, overrides=ov)


def cmd_parametri(args):
    p = _load(args)
    print(f"{'parametro':42} {'valore':>18}  {'evidenza':12} fonti")
    for key, e in p.items():
        val = e["value"]
        val = f"{val:g} {e.get('unit', '')}" if isinstance(val, (int, float)) and not isinstance(val, bool) else str(val)
        print(f"{key:42} {val:>18}  {e.get('evidence', '-'):12} {', '.join(e.get('refs') or [])}")
    print("\nRiferimenti:")
    for k, r in p.references.items():
        print(f"  [{k}] {r['citation']}  PMID {r.get('pmid', '-')}")


def cmd_tavola(args):
    from .pipeline import render_plate
    p = _load(args)
    out = render_plate(p, args.tavola, args.uscita, views=args.viste, width=args.risoluzione,
                       samples=args.campioni, spacing=args.voxel, lang=args.lingua,
                       labels=not args.senza_etichette, background=args.sfondo, export_glb=args.glb,
                       device=args.dispositivo)
    for f in out:
        print(f)


def cmd_atlante(args):
    from .pipeline import PLATES, render_plate
    for name in args.tavole or list(PLATES):
        p = _load(args)
        for f in render_plate(p, name, args.uscita, width=args.risoluzione, samples=args.campioni,
                              spacing=args.voxel, lang=args.lingua, labels=not args.senza_etichette,
                              background=args.sfondo, export_glb=args.glb,
                              device=args.dispositivo):
            print(f)


def cmd_volto(args):
    from .volto.tavole import render_face_plate
    for f in render_face_plate(args.tavola, args.uscita, views=args.viste, width=args.risoluzione,
                               samples=args.campioni, spacing=args.voxel, lang=args.lingua,
                               device=args.dispositivo):
        print(f)


def main(argv=None):
    from .pipeline import PLATES, VIEW_NAMES

    ap = argparse.ArgumentParser(prog="atlas3d", description="Generatore di tavole anatomiche 3D del naso")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("parametri", help="mostra parametri, evidenza e fonti")
    _common(sp)
    sp.set_defaults(func=cmd_parametri)

    sp = sub.add_parser("tavola", help="renderizza una tavola")
    sp.add_argument("tavola", choices=sorted(PLATES))
    sp.add_argument("--viste", nargs="+", choices=VIEW_NAMES)
    _common(sp)
    _render_args(sp)
    sp.set_defaults(func=cmd_tavola)

    sp = sub.add_parser("atlante", help="renderizza tutte le tavole")
    sp.add_argument("--tavole", nargs="+", choices=sorted(PLATES))
    _common(sp)
    _render_args(sp)
    sp.set_defaults(func=cmd_atlante)

    sp = sub.add_parser("volto", help="tavole del volto intero (anatomia BodyParts3D)")
    sp.add_argument("tavola", choices=["volto_cute", "volto_emidissezione", "volto_muscoli"])
    sp.add_argument("--viste", nargs="+", choices=VIEW_NAMES)
    sp.add_argument("--uscita", default="output", type=Path)
    sp.add_argument("--risoluzione", type=int, default=1400)
    sp.add_argument("--campioni", type=int, default=64)
    sp.add_argument("--voxel", type=float, default=0.6)
    sp.add_argument("--lingua", default="it", choices=["it", "en"])
    sp.add_argument("--dispositivo", default="cpu", choices=["cpu", "gpu"])
    sp.set_defaults(func=cmd_volto)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except ParameterError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
