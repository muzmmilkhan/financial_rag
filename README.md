# Financial RAG

Ask questions about financial PDFs. Pages are turned into images, embedded with Gemini, stored in Qdrant, and the best-matching pages are sent to Gemini to write the answer.

```
financial_rag/
├── backend/            FastAPI app (API + PDF ingestion)
│   └── app/
│       ├── main.py          API routes: /health /query /upload
│       ├── ingestion.py     watches data/ and embeds new PDFs
│       ├── pdf.py           PDF -> page images
│       ├── embedder.py      Gemini embeddings
│       ├── vector_store.py  Qdrant read/write
│       ├── llm.py           Gemini answer generation
│       └── config.py        settings from environment variables
├── frontend/           Static web UI (HTML/CSS/JS)
├── data/               Put your PDFs here
├── docker-compose.yml       Local: Qdrant + backend + frontend
├── docker-compose.prod.yml  AWS/EC2: adds the SQS worker, uses ECR images
├── .github/workflows/       CI/CD pipeline (GitHub Actions)
└── .env                Your secrets (you create this)
```

## Setup (3 steps)

**You need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and a free [Gemini API key](https://aistudio.google.com/apikey).

**1. Add your API key**

```bash
cp .env.example .env
```

Open `.env` and replace `your-gemini-api-key` with your real key.

**2. Start everything**

```bash
docker compose up --build
```

**3. Open the app**

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

That's it. The first start is slow because the PDFs already in `data/` are being embedded. Watch the logs (`page 3/120 ...`). Questions return answers once at least one page is indexed.

## Using it

- **Ask:** type a question in the UI (e.g. "What was JPMorgan's net income in 2023?").
- **Add documents:** use the *Upload* tab, or just drop a `.pdf` into `data/`. It is picked up within seconds. Already-processed files are skipped.

## Everyday commands

| Task | Command |
| --- | --- |
| Start in background | `docker compose up -d` |
| Stop | `docker compose down` |
| View backend logs | `docker compose logs -f backend` |
| Wipe the vector database | `docker compose down -v` and delete `data/.processed_files.json` |

## How it works

1. **Ingest:** the backend scans `data/` every 5s. New PDF -> each page becomes an image -> Gemini embeds it -> saved in Qdrant.
2. **Ask:** your question is embedded -> Qdrant finds the most similar pages -> Gemini reads those page images and answers.

## Settings (optional, in `.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | required | Your Gemini key |
| `LLM_MODEL` | `gemini-2.5-pro` | Model that writes answers |
| `EMBEDDING_MODEL` | `gemini-embedding-2` | Model that embeds pages |

## Run without Docker (for development)

Needs Python 3.12, [poppler](https://poppler.freedesktop.org/) (`brew install poppler`), and Qdrant (`docker run -p 6333:6333 qdrant/qdrant`).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your-key DATA_DIR=../data
uvicorn app.main:app --reload --port 8000
```

In another terminal: `cd frontend && python3 -m http.server 3000`

## Troubleshooting

- **`Set GEMINI_API_KEY in .env`**: you skipped step 1.
- **UI shows "Offline"**: backend isn't up; check `docker compose logs backend`. The UI calls the backend through `/api` (proxied by nginx).
- **Rate limit (429) messages**: normal on free keys; ingestion retries automatically.

---

# Deploy to AWS (S3 + SQS + EC2 + GitHub Actions)

```
Browser -> EC2 (nginx -> backend) -> S3 bucket --event--> SQS queue -> worker (EC2) -> Qdrant
git push -> GitHub Actions -> build images -> ECR -> self-hosted runner on EC2 -> docker compose up
```

Use one AWS region everywhere (examples use `eu-north-1`). Replace `ACCOUNT` with your 12-digit AWS account id and `YOUR-BUCKET` with a unique bucket name.

## 1. SQS queue and S3 bucket

1. **SQS** -> Create queue -> Standard, name `financial-rag-queue`, *Visibility timeout* 15 minutes. Under *Access policy* choose Advanced and paste:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": {"Service": "s3.amazonaws.com"},
       "Action": "sqs:SendMessage",
       "Resource": "arn:aws:sqs:eu-north-1:ACCOUNT:financial-rag-queue",
       "Condition": {"ArnLike": {"aws:SourceArn": "arn:aws:s3:::YOUR-BUCKET"}}
     }]
   }
   ```
   Copy the queue **URL**.
2. **S3** -> Create bucket `YOUR-BUCKET` (keep it private). Then *Properties -> Event notifications -> Create*: event type **All object create events**, suffix `.pdf`, destination **SQS queue** `financial-rag-queue`.

## 2. ECR repositories

ECR -> Create repository, twice: `financial-rag-backend` and `financial-rag-frontend`.

## 3. IAM

**a) Role for EC2** (IAM -> Roles -> Create role -> AWS service -> EC2), name it `financial-rag-ec2`, add this inline policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "arn:aws:s3:::YOUR-BUCKET/*"},
    {"Effect": "Allow", "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
     "Resource": "arn:aws:sqs:eu-north-1:ACCOUNT:financial-rag-queue"},
    {"Effect": "Allow", "Action": ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"], "Resource": "*"}
  ]
}
```
**b) User for GitHub Actions**: IAM -> Users -> Create `github-actions`, attach `AmazonEC2ContainerRegistryPowerUser`, then create an **access key** (use case "third-party service").

## 4. EC2 server

1. Launch an instance: Ubuntu 22.04, **t3.large** or bigger (PDF-to-image needs RAM), 30 GB disk, *IAM instance profile* = `financial-rag-ec2`.
2. Security group inbound: **22** (SSH, your IP only) and **80** (HTTP, anywhere).
3. SSH in and install Docker and the AWS CLI:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 unzip curl
   sudo usermod -aG docker ubuntu
   curl -s https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscli.zip && unzip -q awscli.zip && sudo ./aws/install
   newgrp docker
   ```
4. Install the **GitHub self-hosted runner**: repo -> *Settings -> Actions -> Runners -> New self-hosted runner* -> Linux. Run the commands GitHub shows (download, then `./config.sh ...`), and finally:
   ```bash
   sudo ./svc.sh install && sudo ./svc.sh start
   ```

## 5. GitHub repository and secrets

1. Create a GitHub repo and push (see **Branches** below).
2. *Settings -> Secrets and variables -> Actions -> New repository secret*, add:

| Secret | Value |
| --- | --- |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | the `github-actions` user key |
| `AWS_REGION` | e.g. `eu-north-1` |
| `GEMINI_API_KEY` | your Gemini key |
| `S3_BUCKET_NAME` | `YOUR-BUCKET` |
| `SQS_QUEUE_URL` | the queue URL from step 1 |

## 6. Deploy

Push to `main` (or run the workflow from the *Actions* tab). The pipeline builds both images, pushes them to ECR, and the EC2 runner pulls and starts them. Open `http://<EC2-public-IP>` when it turns green.

Test: Upload tab -> pick a PDF -> on EC2 run `docker compose -p financial_rag logs -f worker` and watch it ingest.

## Branches

- `main` = local-only version. Pushing to `main` triggers the pipeline, so **merge `aws-deploy` into `main` only when AWS is ready**.
- `aws-deploy` = all the AWS work (S3 upload, SQS worker, ECR/EC2 workflow).

```bash
git remote add origin https://github.com/YOU/financial_rag.git
git push -u origin main aws-deploy
# open a Pull Request aws-deploy -> main and merge it: the merge deploys.
```

## AWS troubleshooting

- **Upload fails with S3 error:** the EC2 role lacks `s3:PutObject`, or `S3_BUCKET_NAME` is wrong.
- **Worker idle after upload:** check the S3 event notification and the SQS access policy, then `docker compose -p financial_rag logs worker`.
- **Deploy job waits forever:** the runner is offline; run `sudo ./svc.sh status` in the runner folder.
- **Security:** the UI has no login. Add HTTPS/auth before sharing the URL publicly. Stop the instance when unused to save cost.
