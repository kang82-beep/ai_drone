"""Run one flight end to end: analysis → address link → verdicts → anomaly shapes →
cause estimation and draft work orders → web console data.

  python run_flight.py --input <촬영 폴더> --output results/<비행> --config <설정.json>
  python run_flight.py --output results/<비행>                 # analysis already there
  python serve_console.py                                     # then open the console

A step is skipped when its output is newer than its inputs; --force <step> (or all)
re-runs it and every step after it. --calibrate refits the camera corrections in the
address-link step (new camera, site or flight speed). The LLM review in the orders
step follows LLM_MODEL / LLM_SEND_IMAGES in the config and needs OPENAI_API_KEY.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ['analyze', 'register', 'verdicts', 'patterns', 'orders', 'web']


def newest(paths):
    times = [p.stat().st_mtime for p in paths if p.exists()]
    return max(times) if times else 0.0


def plan(out, args, llm):
    reg, verdicts, patterns, orders = out / 'reg', out / 'verdicts', out / 'patterns', out / 'orders'
    py = [sys.executable]
    analyze = py + ['run_full_site.py', '--output', str(out)]
    if args.input:
        analyze += ['--input', str(args.input)]
    if args.config:
        analyze += ['--config', str(args.config)]
    register = py + ['register_flight.py', '--analysis', str(out)] + (['--calibrate'] if args.calibrate else [])
    order_cmd = py + ['generate_orders.py', '--registration', str(reg), '--verdicts', str(verdicts),
                      '--patterns', str(patterns / 'anomaly_patterns.csv'), '--output', str(orders), '--db', str(args.db)]
    if llm.get('LLM_MODEL'):
        order_cmd += ['--llm-model', llm['LLM_MODEL'], '--llm-max', str(llm.get('LLM_MAX_MODULES', 60))]
        if llm.get('LLM_SEND_IMAGES'):
            order_cmd += ['--llm-send']
    return [  # name, command, inputs, outputs
        ('analyze', analyze, [], [out / 'master_results.csv', out / 'run_summary.json']),
        ('register', register, [out / 'master_results.csv'], [reg / 'master_linked.csv', reg / 'registration_report.json']),
        ('verdicts', py + ['judge_modules.py', '--linked', str(reg / 'master_linked.csv'), '--output', str(verdicts)],
         [reg / 'master_linked.csv'], [verdicts / 'module_verdicts.csv', verdicts / 'string_verdicts.csv']),
        ('patterns', py + ['classify_anomaly_patterns.py', '--master', str(reg / 'master_linked.csv'), '--output', str(patterns)],
         [reg / 'master_linked.csv'], [patterns / 'anomaly_patterns.csv']),
        ('orders', order_cmd, [verdicts / 'module_verdicts.csv', patterns / 'anomaly_patterns.csv', ROOT / 'pv_inspector' / 'data' / 'knowledge_base.json'],
         [orders / 'diagnoses.json', orders / 'orders.json', orders / 'summary.json']),
        ('web', py + ['export_web_data.py', '--analysis', str(out), '--registration', str(reg), '--verdicts', str(verdicts),
                      '--patterns', str(patterns / 'anomaly_patterns.csv'), '--orders', str(orders)],
         [orders / 'summary.json', reg / 'master_linked.csv'], [ROOT / 'web' / 'data' / 'site.js']),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', required=True, help='비행 결과 폴더 (results/<비행>)')
    parser.add_argument('--input', help='촬영 영상 폴더 (분석이 아직 없을 때)')
    parser.add_argument('--config', help='분석 설정 JSON (LLM_MODEL 등도 여기서 읽음)')
    parser.add_argument('--calibrate', action='store_true', help='카메라 보정값을 이 비행으로 다시 맞춘다')
    parser.add_argument('--force', choices=STEPS + ['all'], help='이 단계부터 다시 실행')
    parser.add_argument('--db', default=str(ROOT / 'results' / 'history.db'))
    args = parser.parse_args()
    out = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    llm = json.loads(Path(args.config).read_text(encoding='utf-8-sig')) if args.config else {}
    forced = STEPS.index(args.force) if args.force in STEPS else (0 if args.force == 'all' else None)
    log = []
    rerun_after = False
    for i, (name, command, inputs, outputs) in enumerate(plan(out, args, llm)):
        if name == 'analyze' and not args.input and (out / 'master_results.csv').exists() and forced != 0:
            log.append((name, 'skipped', 0.0)); continue
        stale = not all(p.exists() for p in outputs) or newest(inputs) > min(p.stat().st_mtime for p in outputs)
        if not (stale or rerun_after or (forced is not None and i >= forced)):
            log.append((name, 'up to date', 0.0)); continue
        if name == 'analyze' and not args.input:
            raise SystemExit('분석 결과가 없습니다. --input 으로 촬영 폴더를 주세요.')
        print(f'\n=== [{i + 1}/{len(STEPS)}] {name}: {" ".join(command[1:3])} …', flush=True)
        start = time.time()
        code = subprocess.run(command, cwd=ROOT).returncode
        log.append((name, 'done' if code == 0 else f'failed ({code})', time.time() - start))
        if code != 0:
            break
        rerun_after = True  # later steps read what this one just wrote
    print('\n단계별 결과')
    for name, status, seconds in log:
        print(f'  {name:9s} {status:12s} {seconds / 60:6.1f}분' if seconds else f'  {name:9s} {status}')
    summary = out / 'orders' / 'summary.json'
    if summary.exists():
        s = json.loads(summary.read_text(encoding='utf-8'))
        print(f"\n비행 {s['flight_id']}: 현장 작업지시 {s['orders']}건 (모듈 {s['field_modules']}장), 다음 촬영 재확인 {s['recheck_modules']}장, "
              f"GPT {s['llm']}" + (f", 즉시 통보 {len(s['safety_notify'])}장" if s['safety_notify'] else ''))
        print('웹 관제: python serve_console.py  →  http://127.0.0.1:8765')
    if any(status.startswith('failed') for _, status, _ in log):
        sys.exit(1)


if __name__ == '__main__':
    main()
