import yaml

with open('.github/workflows/aprender.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)

for job_name, job in data.get('jobs', {}).items():
    for i, step in enumerate(job.get('steps', [])):
        env = step.get('env', {})
        if env:
            nome = step.get('name', '?')
            print(f'Step {i} ({nome}):')
            for k in env.keys():
                print(f'  - {k}')