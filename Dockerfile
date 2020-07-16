FROM python:3.8-slim

WORKDIR /kx-pdf-tools

# disable tox spinner when running in parallel mode
ENV TOX_PARALLEL_NO_SPINNER=1

RUN \
 apt-get update -y && \
 apt-get install -y python-opencv && \
 apt-get install -y python3.7 && \
 apt-get install -y poppler-utils && \
 apt-get install -y tesseract-ocr && \
 apt-get install -y python3-distutils


COPY . .

RUN \
  pip install --upgrade pip && \
  pip install --no-cache-dir pip tox twine

ENTRYPOINT ["/bin/bash", "test_and_publish.sh"]