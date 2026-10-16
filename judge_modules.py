"""Write module and string verdicts (pv_inspector.module_verdict) for a linked run."""
from pathlib import Path
import argparse, json
import pandas as pd
from pv_inspector.cell_fit import fit_observations
from pv_inspector.module_verdict import judge

ROOT = Path(__file__).resolve().parent


def local(path):
    text = str(path).replace('/', '\\')
    index = text.lower().find('\\results\\')
    return ROOT / text[index + 1:] if index >= 0 else Path(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linked', default='results/shinan3_full_20261030/reg/master_linked.csv')
    parser.add_argument('--catalog', default='shinan3_viewer/assets/module_catalog.csv')
    parser.add_argument('--output', default='results/module_verdicts')
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    linked = pd.read_csv(ROOT / args.linked, encoding='utf-8-sig', low_memory=False)
    catalog = pd.read_csv(ROOT / args.catalog, encoding='utf-8-sig')
    linked['cell_fit'] = fit_observations(linked, local)
    modules, strings = judge(linked, catalog)
    modules.to_csv(output / 'module_verdicts.csv', index=False, encoding='utf-8-sig')
    strings.to_csv(output / 'string_verdicts.csv', index=False, encoding='utf-8-sig')
    (output / 'turn_frames.json').write_text(json.dumps(modules.attrs.get('turn_frames', [])), encoding='utf-8')
    flagged_before = int((modules.flagged_all > 0).sum())
    print(json.dumps({'modules_observed': len(modules), 'flagged_any_view': flagged_before,
                      'cell_fit': linked['cell_fit'].value_counts().to_dict(),
                      'verdicts': modules.verdict.value_counts().to_dict(),
                      'turn_frames': len(modules.attrs.get('turn_frames', [])),
                      'wide_flag': int(modules.wide_flag.sum()),
                      'wide_delta_quantiles': modules.wide_delta.quantile([.01, .5, .99]).round(2).to_dict(),
                      'strings_flagged': strings.loc[strings.string_flag, ['string_id', 'string_delta']].round(2).to_dict('records')},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
