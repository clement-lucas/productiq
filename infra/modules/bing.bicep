// Grounding with Bing Search resource (global). Used by the Market & Trend Scout and Future Tech agents.
param name string
param tags object

resource bing 'Microsoft.Bing/accounts@2020-06-10' = {
  name: name
  location: 'global'
  tags: tags
  kind: 'Bing.Grounding'
  sku: { name: 'G1' }
}

output id string = bing.id
output name string = bing.name
