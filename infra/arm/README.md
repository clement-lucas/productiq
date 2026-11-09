# ARM template

`infra/main.bicep` is the source of truth. The ARM JSON (`azuredeploy.json`) is compiled from it so both formats always match:

- **Automatically:** the `build-arm` GitHub Actions workflow compiles the Bicep on every push to `main` that changes `infra/` and commits `infra/arm/azuredeploy.json` + `azuredeploy.parameters.json` back to the repository.
- **Locally:** `./scripts/build-arm.ps1` (runs `az bicep build --file infra/main.bicep --outfile infra/arm/azuredeploy.json`).

Deploy the ARM template (subscription scope):

```powershell
az deployment sub create --location eastus2 `
  --template-file infra/arm/azuredeploy.json `
  --parameters @infra/arm/azuredeploy.parameters.json
```

Edit `azuredeploy.parameters.json` first (`deployerPrincipalId` = `az ad signed-in-user show --query id -o tsv`).
