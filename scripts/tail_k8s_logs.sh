#!/bin/bash

# Get all pods
pods=$(kubectl get pods -o jsonpath='{.items[*].metadata.name}')

# Function to tail logs for a pod
tail_logs() {
    pod=$1
    kubectl logs -f $pod &
}

# Tail logs for each pod
for pod in $pods
do
    tail_logs $pod
done

# Wait for all background processes
wait
