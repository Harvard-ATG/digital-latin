# syntax=docker/dockerfile:1
FROM docker.io/continuumio/miniconda3:latest

WORKDIR /

# gcc is for build psutil in MacOS
RUN apt-get update && apt-get install -y runit gcc

# create conda environment
# THere conda is being created with pip and pip si being use to install the packages on each of the line stating with pip installpromptflow==1.189.1
# So we need to make sure everything that is in requirements is install here too or that this uses requirements.txt
#  BELOW IS THE REQUIREMENTS.TXT FILE CONTENT, MAKE SURE IT IS IN THE SAME DIRECTORY AS THIS DOCKERFILE
# # This would be used if you're setting up the environment for the entire solution.
# promptflow
# promptflow-sdk # If you use PFClient for flow management/testing
# promptflow-tools
# boto3
# # google-generativeai # For Gemini
# python-dotenv
# # Add any other common packages like pandas, numpy, etc.
# # To manage connection secrets
# pycryptodome
# keyring
# keyrings.alt
# keyrings.cryptfile
# # To export the reports to google drive
# # google-api-python-client
# # google-auth-oauthlib
# # google-auth-httplib2

# RUN conda create -n promptflow-serve python=3.9.16 pip=23.0.1 -q -y && \
#     conda run -n promptflow-serve \
#     pip install promptflow==1.18.1 \
#     promptflow-tools && \
#     conda run -n promptflow-serve pip install keyrings.alt && \
#     conda run -n promptflow-serve pip install gunicorn==22.0.0 && \
#     conda run -n promptflow-serve pip install 'uvicorn>=0.27.0,<1.0.0' && \
#     conda run -n promptflow-serve pip cache purge && \
#     conda clean -a -y
# --- 

COPY backend/requirements.txt .

RUN conda create -n promptflow-serve python=3.9.16 pip=23.0.1 -q -y && \
    conda run -n promptflow-serve \
    pip install promptflow==1.18.1 \
    promptflow-tools && \
    conda run -n promptflow-serve pip install -r requirements.txt && \
    conda run -n promptflow-serve pip install gunicorn==22.0.0 && \
    conda run -n promptflow-serve pip install 'uvicorn>=0.27.0,<1.0.0' && \
    conda run -n promptflow-serve pip cache purge && \
    conda clean -a -y

RUN echo "import os" | cat - /opt/conda/envs/promptflow-serve/lib/python3.9/site-packages/promptflow/core/_serving/v1/blueprint/static_web_blueprint.py > temp && \
mv temp /opt/conda/envs/promptflow-serve/lib/python3.9/site-packages/promptflow/core/_serving/v1/blueprint/static_web_blueprint.py

# # This docker file needs the flow to be in a certain area, so I could theorectically have the first par tpoint to where ever i wnat
## But what is around that flow has to be in the working directory also has to work well.
## So in this case we really need to copy everything in the working directory to the docker image, and that working directory would be 
# ./digital_latin_flows /digital_latin_flows
# COPY ./digital_latin_flows /digital_latin_flows -- USE THIS IF YOU WANT TO COPY THE DIGITAL LATIN FLOWS

# -- WAS ORIGINAL, BUT I THINK IT IS BETTER TO COPY THE DIGITAL LATIN FLOWS, SO IGNORED THIS LINE
# COPY ./flow /flow
COPY backend /backend/

# The following line is to make sure that the python path is set correctly and includes the digital_latin_flows and _connections_manager_ directories.
ENV PYTHONPATH='${PYTHONPATH}:/backend'
RUN echo "PYTHONPATH is: $PYTHONPATH"

EXPOSE 8080

# This is I'm not sure if this is needed, but it is in the original docker file
# Temporarily removing for now.
# COPY ./connections /connections

# reset runsvdir
RUN rm -rf /var/runit
COPY backend/runit /var/runit
# grant permission
RUN chmod -R +x /var/runit

COPY backend/start.sh ./start.sh

RUN chmod +x ./start.sh

CMD ["bash", "./start.sh"]
