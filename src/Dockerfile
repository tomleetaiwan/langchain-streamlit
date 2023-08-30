
FROM python:3.11-slim

WORKDIR /app

# UPDATE APT-GET
RUN apt-get update

# INSTALL OTHER UTILITIES
RUN apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git        

# INSTALL ODBC DRIVER for DEBIAN 10
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update && ACCEPT_EULA=Y apt-get -y install msodbcsql17 msodbcsql17
RUN apt-get update && ACCEPT_EULA=Y apt-get -y install mssql-tools msodbcsql17

# CONFIGURE ENV FOR /bin/bash TO USE MSODBCSQL17
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile 
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc 

# INSTALL unixODBC DEVELOPEMENT HEADER
RUN apt-get install -y unixodbc-dev

# REMOVE APT-GET DOWNLOADED PACKAGE INFORMATION
RUN rm -rf /var/lib/apt/lists/*

# COPY SOURCE CODE AND CONFIG FILES
COPY . /app

# INSTALL PYTHON DEPENDENCIES
RUN pip3 install -r requirements.txt

# EXPOSE PORT
EXPOSE 8501

# HEALTHCHECK
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# RUN STREAMLIT
ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]