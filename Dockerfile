FROM ubuntu:14.04
MAINTAINER Avi "avi@shippable.com"

ENV DEBIAN_FRONTEND noninteractive
RUN dpkg-divert --local --rename --add /sbin/initctl
RUN locale-gen en_US en_US.UTF-8
RUN dpkg-reconfigure locales
RUN echo "deb http://archive.ubuntu.com/ubuntu trusty main universe restricted multiverse" > /etc/apt/sources.list

# force all apt-get commands with a yes
ADD 90forceyes /etc/apt/apt.conf.d/

RUN mkdir -p /root/setup
ADD containerSetup.sh /root/setup/
RUN /bin/bash /root/setup/containerSetup.sh
