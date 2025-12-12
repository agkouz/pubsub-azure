FROM python:3.13-alpine
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY . /code/app
CMD ["python3", "app/main.py"]
# CMD ["/bin/bash"]
