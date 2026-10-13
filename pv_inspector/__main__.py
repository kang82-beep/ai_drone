"""Command line entry point; validation does not load the neural networks."""
import argparse
from . import config


def main():
    parser = argparse.ArgumentParser(description="Drone thermal PV inspector")
    parser.add_argument('--config', help='JSON settings file')
    parser.add_argument('--input', help='Override INPUT_IMG_DIR from the config file')
    parser.add_argument('--output', help='New or empty output directory')
    parser.add_argument('--check', action='store_true', help='Validate required input paths only')
    parser.add_argument('--gui', action='store_true', help='Open the desktop operations window')
    args = parser.parse_args()
    if args.gui:
        from .desktop import main as desktop_main
        desktop_main()
        return
    try:
        config.configure(args.config, args.output, args.input)
        config.validate_inputs()
        if args.check:
            print('Required input paths OK')
            return
        from .pipeline import main as run
        run()
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
