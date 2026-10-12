"""Secrets never enter requests persisted in the research artifacts."""
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'formula_lab' / 'data'
RUNTIME = ROOT / '.formula-runtime'
RUNTIME.mkdir(exist_ok=True)
CONFIG = json.loads((ROOT / 'formula_lab/config.json').read_text())
load_dotenv(Path.home() / '.config/rag-formula/openrouter.env', override=False)
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
import litellm
litellm.suppress_debug_info = True


def completion(messages):
    response = litellm.completion(
        model='openrouter/' + CONFIG['chat_model'], messages=messages,
        api_key=os.environ.get('OPENROUTER_API_KEY'), temperature=0,
        max_tokens=2500, timeout=90, num_retries=2,
        response_format={'type':'json_object'},
    )
    raw = response.choices[0].message.content or '{}'
    metadata = {'model':response.model, 'usage':response.usage.model_dump(),
                'provider':response.model_dump().get('provider',response._hidden_params.get('custom_llm_provider')),
                'response_cost':response._hidden_params.get('response_cost'),
                'response_id':response.id}
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = {'blocked': True, 'parse_error': 'invalid_json'}
    return parsed, metadata


def embeddings(texts):
    result = litellm.embedding(
        model='openrouter/' + CONFIG['embedding_model'], input=texts,
        api_key=os.environ.get('OPENROUTER_API_KEY'), timeout=90, num_retries=2,
    )
    return [x['embedding'] for x in sorted(result.data,key=lambda x:x['index'])]


if __name__ == '__main__':
    import sys
    if '--smoke' in sys.argv:
        try:
            x, m = completion([{'role':'user','content':'Return JSON {"ok":true}'}])
            v = embeddings(['Kiểm định áp suất'])
            print(json.dumps({'chat':x,'model':m['model'],'embedding_dimensions':len(v[0])}))
        except Exception as e:
            print(json.dumps({'error_type':type(e).__name__,'status':getattr(e,'status_code',None)}))
            sys.exit(1)
