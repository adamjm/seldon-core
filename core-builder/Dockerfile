FROM openjdk:8u141-jdk

# install docker
RUN \
    apt-get update && \
    apt-get install -y \
         apt-transport-https \
         ca-certificates \
         curl \
         gnupg2 \
         software-properties-common 

ARG ARCH=ppc64el
RUN echo ${ARCH} ARCH
RUN echo $(. /etc/os-release; echo "$ID")
RUN echo $(lsb_release -cs)
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && \
    add-apt-repository \
       "deb [arch=${ARCH}] https://download.docker.com/linux/ubuntu \
       xenial \
       stable" && \
       cat /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y docker-ce

RUN \
    apt-get update -y && \
    apt-get install -y vim && \
    apt-get install -y build-essential && \
    apt-get install -y maven && \
    update-alternatives --set java /usr/lib/jvm/java-8-openjdk-${ARCH}/jre/bin/java && \
    apt-get remove -y --auto-remove && apt-get clean -y && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# dependencies for release script
RUN \
    # install env for python3
    apt-get update -y && \
    apt-get install -y python3-pip && \
    pip3 install pyyaml && \
    apt-get remove -y --auto-remove && apt-get clean -y && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /work

# Define default command.
CMD ["bash"]

