FROM python:3.11-slim

WORKDIR /app

# INSTALL UTILITIES AND MSODBCSQL18 DRIVER FOR DEBIAN 11
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gnupg-agent \
    curl \
    git \
    software-properties-common && \
    rm -rf /var/lib/apt/lists/*
    
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
    
RUN apt-get update && \
    env ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools && \
    rm -rf /var/lib/apt/lists/*

# CONFIGURE ENV FOR /bin/bash TO USE MSODBCSQL18
SHELL ["/bin/bash", "-c"]
RUN echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bash_profile && \
    echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc

# COPY SOURCE CODE AND CONFIG FILES
COPY . /app

# INSTALL PYTHON DEPENDENCIES
RUN pip3 install --no-cache-dir -r requirements.txt

# EXPOSE PORT
EXPOSE 8501

# HEALTHCHECK
HEALTHCHECK CMD ["curl", "--fail", "http://localhost:8501/_stcore/health"]

# RUN STREAMLIT
ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]