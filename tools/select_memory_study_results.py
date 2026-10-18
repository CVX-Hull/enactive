#!/usr/bin/env python3
"""Publish the study's illustrative projection, preserving full-report provenance.

Run after two complete frozen collections named final-r2/final-r3 under --runs.
This overwrites only the versioned selected JSON; it never changes raw evidence.
It is a historical presentation recipe, not a performance-selection procedure or
an alternative reader for older study formats. Review the output in Git.
"""
import hashlib
import json
from pathlib import Path

import argparse

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--runs", type=Path, default=ROOT / ".runtime/research/memory-representations/runs")
args = parser.parse_args()
base = args.runs.resolve()
if not base.is_relative_to((ROOT / ".runtime").resolve()):
    raise ValueError("Study reports must remain project-local")
r=json.loads((base/'final-r2/report.json').read_text())
replica=json.loads((base/'final-r3/report.json').read_text())
assert r['status'] == replica['status'] == 'completed'
assert r['manifest']['protocol'] == replica['manifest']['protocol'] == 'memory-study-v1.1'
assert r['manifest']==replica['manifest'] and r['content']==replica['content']
assert r['raw_sha256']==replica['raw_sha256']
groups=r['content']['groups']
choices={
'E': {
 'q=0.8:rho=0.0:n=4:copies=1','q=0.8:rho=0.0:n=4:copies=16',
 'q=0.8:rho=0.75:n=12:copies=1','q=0.6:rho=0.75:n=12:copies=16',
 'q=0.95:rho=0.0:n=1:copies=1'},
'C': {'outcomes=rare-update;source=normal;session=normal;visibility=full;k=4',
       'outcomes=all-allow;source=normal;session=normal;visibility=masked;k=4',
       'outcomes=all-allow;source=normal;session=normal;visibility=masked;k=8',
       'outcomes=all-allow;source=normal;session=normal;visibility=masked;k=16'},
'D': {'drift:phase=3','no_drift:probe_after_phase=3','context_irrelevant:phase=4','hidden_domain:phase=2'}
}
metrics={
'E': ('brier','log_loss','wrong_high_confidence','abstained','expected_regret','realized_utility','width','contains_true_model_posterior','replay_forecast_change','replay_decision_change'),
'C': ('queries','known_answers','decision_correct','answer_correct','avoidable_abstentions','unsupported_answers','wrong_answers','rare_queries','rare_known_answers','rare_answer_correct','updated_queries','updated_known_answers','updated_answer_correct','required_latest_sources','latest_source_lineage_recalled','latest_records_recalled','retained_record_bytes','lineage_bytes','sqlite_database_bytes','fts_document_rows_constructed','metadata_rows_constructed'),
'D': ('brier','first16_brier','last16_brier','probability_error','retention_error_change','state_bytes')
}
selected=[]
for group in groups:
    suite=group['suite']
    if suite not in choices or group['condition'] not in choices[suite]:continue
    if group['kind']=='paired' and not (suite=='D' and group['condition']=='context_irrelevant:phase=4' and group['method']=='scoped-minus-pooled'):continue
    if suite=='C':
        if group['method'] not in ('exact','fts5','recent','reservoir','majority-depth1','truncation-depth1'):continue
        if group['condition'].endswith(('k=8','k=16')) and group['method'] not in ('exact','fts5'):continue
    selected.append({k:group[k] for k in ('suite','kind','condition','method')} | {
        'metrics':{name:{k:group['metrics'][name][k] for k in ('n_seeds','mean','mc_half_width')}
                   for name in metrics[suite] if name in group['metrics']}})
lineage=[]
for regime in ('literal','permuted_final'):
    for passes in (1,4,16):
        for method in ('archive_replay','incremental_view'):
            cases=[g for g in groups if g['kind']=='absolute' and g['suite']=='L' and g['method']==method and g['condition'].startswith(regime+'/') and g['condition'].endswith(f'/passes={passes}')]
            assert len(cases)==12
            lineage.append({'regime':regime,'passes':passes,'method':method,'templates':12,
              'sum_of_template_means':{name:sum(g['metrics'][name]['mean'] for g in cases)
                for name in ('queries','mismatches','total_work','archive_bytes','extra_state_bytes')}})
result={
 'protocol':r['manifest']['protocol'],'source_commit':r['manifest']['git_commit'],
 'source_sha256':r['manifest']['source_sha256'],
 'environment':{k:r['manifest'][k] for k in ('python','sqlite','system','machine')},
 'seeds':{'first':10000,'last':10255,'count':256},'row_counts':r['content']['row_counts'],
 'content_sha256':r['content_sha256'],'raw_sha256':r['raw_sha256'],'raw_bytes':r['raw_bytes'],
 'repeat_content_and_raw_equal':True,'raw_files':[
   '.runtime/research/memory-representations/runs/final-r2/seed-aggregates.jsonl.gz',
   '.runtime/research/memory-representations/runs/final-r3/seed-aggregates.jsonl.gz'],
 'interpretation':'Illustrative subset, not an across-regime ranking. Full declared matrix ran; local complete reports and compressed raw rows retained. MC half-widths are descriptive across independent seed aggregates, not native efficacy or simultaneous significance. L sums describe twelve separate templates, not one game heap.',
 'lineage_batches':lineage,'selected_groups':selected,
 'causal_negative_control':r['content']['causal_negative_control'],
 'full_report_sha256':{f'final-r{i}':hashlib.sha256((base/f'final-r{i}/report.json').read_bytes()).hexdigest() for i in (2,3)}
}
out=ROOT / 'docs/assets/memory-study-results.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n')
print(json.dumps({'selected_groups':len(selected),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
