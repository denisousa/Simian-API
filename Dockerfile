# Use Ubuntu as base image since we need to install TXL and NiCad
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, pip and other required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    make \
    gcc \
    flex \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install TXL (required for NiCad)
WORKDIR /tmp
RUN wget https://www.txl.ca/download/18359-txl10.8b.linux64.tar.gz \
    && tar xzf 18359-txl10.8b.linux64.tar.gz \
    && cd txl10.8b.linux64 \
    && ./InstallTXL \
    && rm -rf /tmp/txl10.8b.linux64*

# Set up working directory
WORKDIR /app

# Copy the entire project
COPY . /app

# Install Python dependencies
RUN pip3 install -e .

# Build NiCad
WORKDIR /app/NiCad
RUN make

# Set back to app directory
WORKDIR /app

# Set environment variable for NiCad path
ENV NICAD_HOME=/app/NiCad

# Expose port for Flask API
EXPOSE 5000

# Run Flask API
CMD ["python3", "main.py"]