FROM docker.n8n.io/n8nio/n8n:latest

USER root

# The official n8n image ships without apk; restore it from Alpine (as n8n's Execute Command docs describe).
COPY --from=alpine:3.22 /sbin/apk /sbin/apk
COPY --from=alpine:3.22 /lib/apk /lib/apk
COPY --from=alpine:3.22 /usr/lib/libapk* /usr/lib/

# Python and FFmpeg for the pipeline scripts in /app
RUN apk add --no-cache bash python3 py3-pip ffmpeg

COPY docker/python/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt && rm /tmp/requirements.txt

USER node
