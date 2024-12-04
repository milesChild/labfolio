FROM public.ecr.aws/lambda/python:3.11

# install python packages
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# copy in the function
COPY app.py ${LAMBDA_TASK_ROOT}

# set the CMD to handler
CMD [ "app.handler" ]