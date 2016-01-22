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
RUN apt-get install -yy python-dev software-properties-common python-software-properties;
RUN add-apt-repository -y ppa:ubuntu-toolchain-r/test
RUN echo "deb http://archive.ubuntu.com/ubuntu trusty main universe restricted multiverse" > /etc/apt/sources.list

RUN apt-get update
RUN apt-get install -yy build-essential \
                    g++-4.9 \
                    wget \
                    curl \
                    texinfo \
                    make \
                    openssh-client \
                    sudo \
                    git-core \
                    vim \
                    htop ;

RUN apt-get install python-pip;

RUN echo "================== Installing python requirements ====="
RUN mkdir -p /home/shippable/
ADD . /home/shippable/appBase
RUN pip install -r /home/shippable/appBase/requirements.txt

RUN echo "================= Installing Node ==================="
RUN curl -sL https://deb.nodesource.com/setup_4.x | sudo -E bash -
RUN apt-get update

RUN apt-get install -y nodejs
RUN npm install -g forever grunt grunt-cli

RUN echo "================== Adding empty known hosts file =============="
RUN mkdir -p /root/.ssh
RUN touch /root/.ssh/known_hosts

RUN echo "================== Disabling scrict host checking for ssh ====="
ADD config /root/.ssh/config

RUN echo 'ALL ALL=(ALL) NOPASSWD:ALL' | tee -a /etc/sudoers
