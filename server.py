#!/usr/bin/env python3
"""Tiny Job Tracker API + static file server.

No framework needed. Serves index.html and persists jobs in data/jobs.json.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
JOBS_FILE = DATA_DIR / "jobs.json"

STATUSES = {"saved", "applied", "interviewing", "offered", "rejected", "ghosted"}


def today() -> str:
    return date.today().isoformat()


def load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    try:
        data = json.loads(JOBS_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_jobs(jobs: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    tmp = JOBS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(jobs, indent=2, sort_keys=True) + "\n")
    tmp.replace(JOBS_FILE)


def slug_id(seed: str) -> str:
    import hashlib

    return hashlib.sha1(seed.encode("utf-8", "ignore")).hexdigest()[:12]


def normalize_job(job: dict) -> dict:
    if not isinstance(job, dict):
        raise ValueError("job must be an object")

    now = today()
    title = str(job.get("title") or job.get("jobTitle") or "").strip()
    company = str(job.get("company") or job.get("employer") or "").strip()
    url = str(job.get("url") or job.get("link") or "").strip()
    status = str(job.get("status") or "saved").strip().lower()
    if status not in STATUSES:
        status = "saved"

    if not title or not company:
        raise ValueError("job requires company and title")

    tags = job.get("tags") or job.get("skills") or []
    if isinstance(tags, str):
        tags = [s.strip() for s in re.split(r"[,\n]", tags) if s.strip()]
    if not isinstance(tags, list):
        tags = []

    date_added = str(job.get("dateAdded") or job.get("date") or now).strip()[:10] or now
    notes = str(job.get("notes") or "").strip()

    normalized = {
        "id": str(job.get("id") or slug_id("|".join([company.lower(), title.lower(), url.lower()]))),
        "company": company,
        "title": title,
        "url": url,
        "location": str(job.get("location") or "").strip(),
        "salary": str(job.get("salary") or "").strip(),
        "status": status,
        "priority": str(job.get("priority") or "medium").strip().lower(),
        "resume": str(job.get("resume") or job.get("resumeUsed") or "").strip(),
        "contact": str(job.get("contact") or job.get("recruiter") or "").strip(),
        "source": str(job.get("source") or "").strip(),
        "tags": [str(t).strip() for t in tags if str(t).strip()],
        "notes": notes,
        "dateAdded": date_added,
        "history": job.get("history") if isinstance(job.get("history"), list) else [
            {"status": status, "date": date_added, "note": "Created via API"}
        ],
    }
    if normalized["priority"] not in {"high", "medium", "low"}:
        normalized["priority"] = "medium"
    return normalized


class Handler(SimpleHTTPRequestHandler):
    server_version = "JobTracker/1.0"

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_json(self, status: int, payload):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode() or "{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/jobs":
            self.send_json(200, load_jobs())
            return
        if path in {"/", ""}:
            self.path = "/index.html"
        return super().do_GET()

    def do_PUT(self):
        if urlparse(self.path).path != "/api/jobs":
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            if not isinstance(payload, list):
                raise ValueError("expected an array of jobs")
            jobs = [normalize_job(j) for j in payload]
            save_jobs(jobs)
            self.send_json(200, {"ok": True, "count": len(jobs)})
        except Exception as e:
            self.send_json(400, {"ok": False, "error": str(e)})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/jobs", "/api/import"}:
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            incoming = payload.get("jobs", payload) if isinstance(payload, dict) else payload
            if isinstance(incoming, dict):
                incoming = [incoming]
            if not isinstance(incoming, list):
                raise ValueError("expected a job object or jobs array")

            existing = load_jobs()
            by_id = {j.get("id"): j for j in existing}
            added = 0
            updated = 0
            for item in incoming:
                job = normalize_job(item)
                if job["id"] in by_id:
                    old = by_id[job["id"]]
                    job["history"] = old.get("history") or job["history"]
                    existing[existing.index(old)] = job
                    updated += 1
                else:
                    existing.insert(0, job)
                    added += 1
            save_jobs(existing)
            self.send_json(200, {"ok": True, "added": added, "updated": updated, "count": len(existing)})
        except Exception as e:
            self.send_json(400, {"ok": False, "error": str(e)})

    def translate_path(self, path):
        path = urlparse(path).path
        rel = path.lstrip("/") or "index.html"
        candidate = (ROOT / rel).resolve()
        if not str(candidate).startswith(str(ROOT)):
            return str(ROOT / "index.html")
        return str(candidate)


def main() -> int:
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8787))
    host = os.environ.get("HOST", "0.0.0.0")
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Job tracker running on http://{host}:{port}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
