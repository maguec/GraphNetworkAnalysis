```sql
SELECT 
  TransitNode,
  TotalDownstream,
  OfflineDownstream,
  ROUND(OfflineDownstream / TotalDownstream, 2) AS DownstreamImpactRatio,
  ROUND(OfflineDownstream / 3.0, 2) AS GlobalFaultCoverage,
  ROUND((OfflineDownstream / TotalDownstream) * (OfflineDownstream / 3.0), 4) AS SuspicionScore
FROM (
  -- Standard SQL subquery to group and aggregate the graph results
  SELECT 
    TransitNode,
    COUNT(ConsumerId) AS TotalDownstream,
    COUNTIF(ConsumerId IN ('C_1090', 'C_1119', 'C_1125')) AS OfflineDownstream
  FROM GRAPH_TABLE(
    NetworkGraph
    -- The native GQL traversal
    MATCH 
      (t:TransitNodes)
      -[:Connections_TT]->{0,20}(:TransitNodes)
      -[:Connections_TC]->(c:Consumers)
    COLUMNS (
      t.NodeId AS TransitNode,
      c.NodeId AS ConsumerId
    )
  )
  GROUP BY TransitNode
)
-- Standard SQL filtering and ordering on the aggregated results
WHERE 
  OfflineDownstream > 0
ORDER BY 
  SuspicionScore DESC;
```
