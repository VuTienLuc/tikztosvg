# Máy chủ TikZ → SVG (latex + dvisvgm). Chạy được trên Mac Apple Silicon, Windows, Linux và cloud.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 ghostscript \
      texlive-latex-base texlive-latex-recommended texlive-latex-extra \
      texlive-pictures texlive-science texlive-lang-other texlive-fonts-recommended \
      texlive-binaries \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc/* /usr/share/man/*

RUN useradd --create-home --uid 10001 tikz
WORKDIR /app
COPY server.py /app/server.py
USER tikz

ENV HOST=0.0.0.0 PORT=8765 MAX_JOBS=2 TIMEOUT=40
EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=10s CMD python3 -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/health')"
CMD ["python3", "/app/server.py"]
