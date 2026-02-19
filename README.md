# 초기 두문자 조합 도구 (Mnemonic AIMCP)

이 프로젝트는 한국어 사전(표준국어대사전, 한국어기초사전, 우리말샘)에서 만든 trie를 이용해 **입력된 초성/첫 글자 목록으로 가능한 단어 조합(두문자 조합)** 을 찾습니다. 문장으로 “붙이는” 작업은 LLM이 담당하고, 이 코드는 순수하게 단어 조합만 제공합니다.

## 주요 구성
- `lexicon/mnemo_mcp.py` : 코어 로직(`generate_initial_combos`, `initials_from_words`)과 선택적 MCP 툴.
- `lexicon/trie.py` : trie 자료구조(사전 소스/스코어 포함).
- `lexicon/build_lexicon.py` : 사전 덤프를 읽어 `artifacts/lexicon.jsonl.gz`, `artifacts/trie.pkl` 생성.
- `combosearch_trace_cli.py` : CLI 디버깅/트레이스용.
- `app.py` : FastAPI 게이트웨이(`/combinations/generate`, `/lexicon/validate`).
- `openai-chatkit-starter-app/` : Actions/에이전트 예제 앱.

## 사전 데이터 (저장소에 포함되지 않음)
- 폴더만 비어 있고 원본 데이터는 직접 내려받아야 합니다.
  - `표준국어대사전/`
  - `한국어기초사전/`
  - `우리말샘/`
- 저장소/컨테이너 크기 문제로 Git에 올리지 않습니다. 위 폴더에 데이터를 넣은 뒤 아래 빌드 스텝을 실행하세요.

## 로컬 환경 준비
```bash
python -m venv .venv
.\.venv\Scripts\activate      # PowerShell
pip install -r requirements.txt
```

## Lexicon / Trie 빌드
사전 덤프가 각 폴더에 있다고 가정:
```bash
python -m lexicon.build_lexicon ^
  --dict-dir .\표준국어대사전 ^
  --jsonl-out .\artifacts\lexicon.jsonl.gz ^
  --trie-out  .\artifacts\trie.pkl
```
실행 후 요약 리포트와 `trie.pkl` 이 생성됩니다.

## 조합 찾기 (CLI)
```bash
# 순서 유지
python combosearch_trace_cli.py 결 근 신 상 --beam 64 --max 20
# 순서 무시(bag mode)
python combosearch_trace_cli.py 결 근 신 상 --bag-mode --beam 64 --max 20
```
결과는 `combo`, `words`, `score`, `mode`, `coverage` 필드로 표시됩니다.

## FastAPI 게이트웨이
```bash
uvicorn app:app --host 0.0.0.0 --port 8080
```
- OpenAPI: `http://localhost:8080/openapi.json`
- 엔드포인트:
  - `POST /combinations/generate` (구 alias: `/mnemonics/generate`)
  - `POST /lexicon/validate`
- `MNEMONIC_API_KEY` 환경 변수를 설정하면 API Key 헤더 검사를 활성화합니다. 설정하지 않으면 인증 없이 동작합니다.

## MCP 서버 (선택)
환경변수로 HTTP 전송을 켜거나 기본 STDIO로 실행할 수 있습니다.
```bash
# HTTP (Streamable HTTP)
$env:MCP_TRANSPORT="http"
$env:MCP_HOST="0.0.0.0"
$env:MCP_PORT="8000"
$env:MCP_PATH="/mcp"
python -m lexicon.mnemo_mcp
# 또는 STDIO
python -m lexicon.mnemo_mcp
```
툴 이름: `initial_combos.suggest`, `initial_combos.from_words`, `lexicon.check_word`, `lexicon.words_starting_with`.

## 컨테이너 빌드 & Cloud Run 배포 요약
Dockerfile은 `uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}` 를 실행합니다. 사전 데이터는 빌드 컨텍스트에서 제외됩니다(`.dockerignore`, `.gcloudignore` 참고).

```bash
# 빌드
$env:PROJECT = (gcloud config get-value project)
gcloud builds submit ^
  --tag "asia-northeast3-docker.pkg.dev/$env:PROJECT/cloud-run-source-deploy/initial-combos:manual" ^
  .

# 배포 (메모리 2Gi 권장: trie 로딩 시 여유)
gcloud run deploy initial-combos ^
  --image "asia-northeast3-docker.pkg.dev/$env:PROJECT/cloud-run-source-deploy/initial-combos:manual" ^
  --region=asia-northeast3 ^
  --allow-unauthenticated ^
  --cpu=1 ^
  --memory=2Gi ^
  --timeout=60s ^
  --concurrency=80 ^
  --min-instances=0 ^
  --max-instances=2
```
배포 후 주소 예: `https://initial-combos-xxxxx-a-wn.a.run.app`. Actions/GPT에서 `servers.url` 로 사용하세요.

## Git에 올리지 않을 항목
사전 원본 덤프(위 세 폴더)와 대용량 중간산출물은 Git에 커밋하지 마세요. 이미 `.dockerignore` / `.gcloudignore` 로 빌드 제외 설정이 되어 있습니다. 필요 시 별도 `.gitignore` 에도 추가해 유지하세요.

