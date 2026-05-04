Try to find the possible RCA from all consumers that are currently showing issues

```sql
SELECT
  TransitNode,
  TotalDownstream,
  OfflineDownstream,
  ROUND( SAFE_DIVIDE(OfflineDownstream, TotalDownstream) * SAFE_DIVIDE(OfflineDownstream, 3.0), 4) AS SuspicionScore,
  ROUND(SAFE_DIVIDE(OfflineDownstream, TotalDownstream), 2) AS DownstreamImpactRatio,
  ROUND(SAFE_DIVIDE(OfflineDownstream, 3.0), 2) AS GlobalFaultCoverage
FROM (
  SELECT
    TransitNode,
    COUNT(ConsumerId) AS TotalDownstream,
    COUNT(
      CASE
        WHEN ConsumerId IN ( SELECT NodeId FROM `Consumers` WHERE Status = 'DOWN') THEN 1
    END
      ) AS OfflineDownstream
  FROM
    GRAPH_TABLE(
        NetworkGraph MATCH(t:TransitNodes)
        -[:Connections_TT]->{0,10}(:TransitNodes)
      -[:Connections_TC]-> (c:`Consumers`)
        COLUMNS(t.NodeId AS TransitNode, c.NodeId AS ConsumerId)
  )
GROUP BY TransitNode)
WHERE OfflineDownstream > 0
ORDER BY SuspicionScore DESC LIMIT 15;
```

Map out the Transit Network

```sql
GRAPH NetworkGraph
MATCH mypath=(p:Producers{NodeId: 'P_10'})-[:Connections_PT]->(t:TransitNodes)-[:Connections_TT]-{0,2}->(t2:TransitNodes)
RETURN SAFE_TO_JSON(mypath) AS JSON
```

