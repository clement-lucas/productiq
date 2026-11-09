// Microsoft Fabric capacity (F SKU). Workspace, lakehouse, notebooks and data agent are created by scripts/fabric/setup_fabric.py.
// TIP: pause the capacity when idle (scripts/fabric-capacity.ps1 -Action Suspend).
param name string
param location string
param sku string = 'F2'
param adminMembers array
param tags object

resource capacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: sku, tier: 'Fabric' }
  properties: {
    administration: { members: adminMembers }
  }
}

output id string = capacity.id
output name string = capacity.name
