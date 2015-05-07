FROM ubuntu:14.04
MAINTAINER Avi "avi@shippable.com"

ENV DEBIAN_FRONTEND noninteractive
RUN dpkg-divert --local --rename --add /sbin/initctl
RUN locale-gen en_US en_US.UTF-8
RUN dpkg-reconfigure locales

# force all apt-get commands with a yes
ADD 90forceyes /etc/apt/apt.conf.d/

RUN echo "================= Installing core binaries ==================="
RUN apt-get update
RUN apt-get install python-dev;
RUN echo "deb http://archive.ubuntu.com/ubuntu trusty main universe restricted multiverse" > /etc/apt/sources.list

RUN apt-get update
RUN apt-get install wget \
                    curl \
                    texinfo \
                    make \
                    openssh-server \
                    openssh-client \
                    gdb \
                    sudo \
                    git-core \
                    g++ \
                    vim \
                    htop \
                    software-properties-common;

RUN apt-get install python-pip \
                    python-software-properties \
                    supervisor ;

RUN echo "================== Installing python requirements ====="
RUN mkdir -p /home/shippable/
ADD . /home/shippable/appBase
RUN pip install -r /home/shippable/appBase/requirements.txt

RUN echo "================= Installing Node ==================="
RUN add-apt-repository ppa:chris-lea/node.js
RUN apt-get update

RUN apt-get install -y nodejs
RUN npm install -g forever grunt grunt-cli

RUN echo "================== Adding empty known hosts file =============="
RUN mkdir -p /root/.ssh
RUN touch /root/.ssh/known_hosts

RUN echo "================== Disabling scrict host checking for ssh ====="
ADD config /root/.ssh/config

RUN echo "================= Adding gclould binaries ============"
RUN mkdir -p /opt/gcloud
ADD google-cloud-sdk /opt/gcloud/google-cloud-sdk
RUN cd /opt/gcloud/google-cloud-sdk && ./install.sh --usage-reporting=false --bash-completion=true --path-update=true
ENV PATH $PATH:/opt/gcloud/google-cloud-sdk/bin
RUN gcloud components update preview

RUN echo 'ALL ALL=(ALL) NOPASSWD:ALL' | tee -a /etc/sudoers
