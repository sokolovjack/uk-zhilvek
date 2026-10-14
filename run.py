#!/usr/bin/env python3
"""Запуск CMS и сайта: http://127.0.0.1:8080/admin/"""
import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
