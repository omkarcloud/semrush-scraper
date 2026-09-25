FROM chetan1111/botasaurus:chrome-151

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt

RUN mkdir app
WORKDIR /app
COPY . /app

EXPOSE 8000

# Real Chrome + Xvfb come with the base image: the keyword tools mint their
# reCAPTCHA token in a headed Chrome; every other endpoint is plain HTTP.
CMD ["python", "run.py"]
