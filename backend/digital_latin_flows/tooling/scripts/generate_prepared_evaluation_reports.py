import os
import json
from datetime import datetime

eval_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '...', 'evaluation', 'llm_as_judge_results')
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '...', 'evaluation', 'prepared_reports', 'evaluation')
os.makedirs(output_dir, exist_ok=True)

# Fixed summaries for judge system prompts
JUDGE_SYSTEM_PROMPT_SUMMARIES = {
    "j1.1": (
        "Evaluates: (1) Content fidelity (same key ideas, no extra details), "
        "(2) Grammar simplification (no more than one dependent/subordinate clause per sentence, no advanced grammatical structures such as deponent verbs, indirect statements, participles, subjunctive, gerunds, gerundives, supines, impersonal passive, double dative), "
        "and (3) Vocabulary appropriateness for first-year Latin students (high-frequency vocabulary, no difficult words)."
    ),
    "j2.1": (
        "Evaluates: (1) Content fidelity (same key ideas, no extra details), "
        "(2) Grammar simplification (no more than two dependent/subordinate clauses per sentence, no advanced grammatical structures such as subjunctive, gerunds, gerundives, supines, impersonal passive, double dative), "
        "and (3) Vocabulary appropriateness for first- and second-year college Latin students (high-frequency vocabulary, no difficult words)."
    ),
}

def get_judge_system_prompt_summary(judge_id):
    judge_id = (judge_id or "").lower()
    if judge_id in JUDGE_SYSTEM_PROMPT_SUMMARIES:
        return JUDGE_SYSTEM_PROMPT_SUMMARIES[judge_id]
    elif judge_id:
        return f"{judge_id.upper()} Judge System Prompt (see original template for full text)"
    else:
        return "Judge System Prompt (see original template for full text)"

def get_judge_system_prompt_csv_refs(judge_id):
    # Map judge_id to relevant CSV filepaths (relative to prompt_data)
    csv_refs = {}
    if judge_id in ("j1.1", "j2.1"):
        csv_refs = {
            "dcc_words": "data/prompt_data/dcc_words.csv",
            "logeion_words": "data/prompt_data/logeion_words.csv"
        }
    return csv_refs

def process_evaluation_report(json_fname):
    json_path = os.path.join(eval_dir, json_fname)
    try:
        with open(json_path, encoding='utf8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[SKIP] {json_fname:30} ... corrupted or unreadable: {e}")
        return

    ts = data.get('timestamp', '')
    eval_id = data.get('evaluation_report_id', '')
    orig = data.get('original_report', {})
    judge = data.get('judge_prompts', {})
    evaluation = data.get('evaluation', {})
    judge_system_id = judge.get('system_prompt_id', '')
    judge_user_id = judge.get('user_prompt_id', '')
    judge_user_prompt = judge.get('user_prompt_used', '').strip()
    model_id = data.get('model', {}).get('model_id', '')
    llm_response = evaluation.get('llm_response', '').strip()
    latency = evaluation.get('evaluation_latency', '')
    token_usage = evaluation.get('token_usage', {})

    csv_refs = get_judge_system_prompt_csv_refs(judge_system_id)
    csv_placeholder = "\n".join([f"- {k}: <see {v}>" for k, v in csv_refs.items()]) if csv_refs else "- No CSV references."

    md_fname = f"evaluation_report_{eval_id:05}.md"
    md_path = os.path.join(output_dir, md_fname)

    md = f"""
# Evaluation Report {eval_id}

**Timestamp:** {ts}

## Original Report
- Report ID: {orig.get('report_id', '')}
- System Prompt ID: {orig.get('system_prompt_id', '')}
- User Prompt ID: {orig.get('user_prompt_id', '')}

## Evaluation
- Model ID: {model_id}
- Latency (seconds): {latency}
- Token Usage: {json.dumps(token_usage, indent=2)}
- Judge System Prompt: {get_judge_system_prompt_summary(judge_system_id)}
- Judge System Prompt CSV Data:
{csv_placeholder}
- Judge User Prompt ID: {judge_user_id}

### Judge User Prompt Used
```
{judge_user_prompt}
```

### LLM Evaluation Response
```
{llm_response}
```
"""
    with open(md_path, 'w', encoding='utf8') as f:
        f.write(md)
    print(f"[OK]   {md_fname:30} ... written successfully")

manifest_path = os.path.join(output_dir, "evaluation_prepared_report_manifest.md")

def load_manifest():
    processed = set()
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf8") as f:
            for line in f:
                if line.startswith("- ") and ".json" in line:
                    parts = line.strip().split()
                    for p in parts:
                        if p.endswith(".json"):
                            processed.add(p)
    return processed

def update_manifest(entries):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(manifest_path, "a", encoding="utf8") as f:
        for entry in entries:
            f.write(f"- {entry['json']} -> {entry['md']} | {entry['status']} | {now}\n")

def main():
    all_jsons = [f for f in os.listdir(eval_dir) if f.endswith('.json')]
    processed_jsons = load_manifest()
    entries = []
    for js in all_jsons:
        md_fname = f"evaluation_report_{int(js.split('_')[-1].split('.')[0]):05}.md"
        md_path = os.path.join(output_dir, md_fname)
        if js in processed_jsons or os.path.exists(md_path):
            print(f"[SKIP] {js:30} ... already processed")
            continue
        process_evaluation_report(js)
        entries.append({"json": js, "md": md_fname, "status": "written"})
    if entries:
        update_manifest(entries)

if __name__ == '__main__':
    main()
