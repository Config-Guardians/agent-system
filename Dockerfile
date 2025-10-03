FROM python:3.12-slim-trixie
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN LATEST_VERSION=$(wget -O - "https://api.github.com/repos/open-policy-agent/conftest/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/' | cut -c 2-)
RUN ARCH=$(arch)
RUN SYSTEM=$(uname)
RUN wget "https://github.com/open-policy-agent/conftest/releases/download/v${LATEST_VERSION}/conftest_${LATEST_VERSION}_${SYSTEM}_${ARCH}.tar.gz"
RUN tar xzf conftest_${LATEST_VERSION}_${SYSTEM}_${ARCH}.tar.gz
RUN mv conftest /usr/local/bin

CMD ["python", "main.py"]
