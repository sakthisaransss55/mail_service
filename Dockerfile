FROM --platform=linux/arm64 python:3.9-slim

WORKDIR /app
COPY . .
RUN pip install -r requirement.txt

EXPOSE 80

CMD ["python", "./mail_sender.py"]