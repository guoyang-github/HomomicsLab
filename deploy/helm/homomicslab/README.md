# HomomicsLab Helm Chart

A minimal Helm chart for deploying HomomicsLab on Kubernetes.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.12+
- Container images for backend and frontend

## Install

```bash
helm install homomicslab ./deploy/helm/homomicslab \
  --set env.HOMOMICS_AUTH_ENABLED=true \
  --set env.HOMOMICS_API_KEY=$HOMOMICS_API_KEY \
  --set secrets.existingSecret=homomicslab-secrets
```

## Create secrets

```bash
kubectl create secret generic homomicslab-secrets \
  --from-literal=OPENAI_API_KEY=$OPENAI_API_KEY
```

## Uninstall

```bash
helm uninstall homomicslab
```
