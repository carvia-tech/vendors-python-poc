# Deployment

## Kubernetes Deployment

Synthesize the k8s output for dev

```shell
export version=1 && export env=dev && cdk8s synth
```

Synthesize the k8s output for prod

```shell
export version=1 && export env=prod && cdk8s synth
```

Apply changes to kubernetes cluster

```shell
kubectl apply -f dist/
```

## Create Kubernetes Secrets

Secrets are stored in sops file, run the below command for creating kubernetes secrets

```shell
sops -d secrets.enc.yaml | kubectl -n dev apply -f -
```
