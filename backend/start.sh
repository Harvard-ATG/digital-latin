#!/bin/bash

# This script is used as the entrypoint for the backend Docker container.
# It helps manage the lifecycle of the container's services.
# stop services created by runsv and propagate SIGINT, SIGTERM to child jobs
sv_stop() {
    echo "$(date -uIns) - Stopping all runsv services"
    for s in $(ls -d /var/runit/*); do
        sv stop $s
    done
}

# register SIGINT, SIGTERM handler which interrupts and terminates all runsv services gracefully
trap sv_stop SIGINT SIGTERM

# start services in background and wait all child jobs
runsvdir /var/runit &
wait
