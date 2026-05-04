import os
import json
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv
from google.cloud import spanner
from nicegui import ui, app

# Load environment variables
load_dotenv(override=True)
GOOGLE_PROJECT = os.getenv("GOOGLE_PROJECT")
GOOGLE_SPANNER_INSTANCE = os.getenv("GOOGLE_SPANNER_INSTANCE")
GOOGLE_SPANNER_DATABASE = os.getenv("GOOGLE_SPANNER_DATABASE")

# Initialize Spanner Client
spanner_client = spanner.Client(project=GOOGLE_PROJECT, disable_builtin_metrics=True)
instance = spanner_client.instance(GOOGLE_SPANNER_INSTANCE)
database = instance.database(GOOGLE_SPANNER_DATABASE)

# Custom CSS for prominent striping
ui.add_head_html('''
    <style>
        .q-table tbody tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .q-table tbody tr:hover {
            background-color: #f1f1f1;
        }
    </style>
''', shared=True)

def query_spanner(query: str) -> List[Dict[str, Any]]:
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(query)
        rows_list = list(results)
        columns = [column.name for column in results.fields] if results.fields else []
        return [dict(zip(columns, row)) for row in rows_list]

def get_blast_radius_data(producer_id: str) -> Dict[str, Any]:
    query = f"""
    GRAPH NetworkGraph
    MATCH mypath=(p:Producers{{NodeId: '{producer_id}'}})-[:Connections_PT]->(t:TransitNodes)-[:Connections_TT]-{{0,2}}->(t2:TransitNodes)
    RETURN SAFE_TO_JSON(mypath) AS JSON
    """
    print(f"\nDEBUG: Executing GSQL Query for {producer_id}:\n{query}")
    rows = query_spanner(query)
    print(f"DEBUG: Query returned {len(rows)} rows")
    
    nodes = {}
    links = []
    seen_links = set()

    for row_idx, row in enumerate(rows):
        raw_json = row.get('JSON')
        if not raw_json: continue
            
        try:
            if isinstance(raw_json, str):
                path_elements = json.loads(raw_json)
            else:
                path_elements = json.loads(json.dumps(raw_json, default=str))
        except Exception as e:
            print(f"DEBUG: Row {row_idx} failed to parse JSON: {e}")
            continue

        if not isinstance(path_elements, list): continue

        print(f"DEBUG: ROW {row_idx} PATH ELEMENTS:")
        for i, element in enumerate(path_elements):
            kind = element.get('kind')
            if kind == 'node':
                props = element.get('properties', {})
                node_id = props.get('NodeId') or str(element.get('identifier'))
                print(f"  [NODE] {node_id}")
                if node_id not in nodes:
                    label = element.get('labels', ['Unknown'])[0]
                    nodes[node_id] = {"id": node_id, "name": f"{label}: {node_id}", "group": label}
            elif kind == 'edge':
                if i > 0 and i < len(path_elements) - 1:
                    src_node, tgt_node = path_elements[i-1], path_elements[i+1]
                    src_id = src_node.get('properties', {}).get('NodeId') or str(src_node.get('identifier'))
                    tgt_id = tgt_node.get('properties', {}).get('NodeId') or str(tgt_node.get('identifier'))
                    label = element.get('labels', ['connected'])[0]
                    print(f"  [EDGE] {src_id} -[{label}]-> {tgt_id}")
                    link_key = (src_id, tgt_id, label)
                    if link_key not in seen_links:
                        links.append({"source": src_id, "target": tgt_id, "type": label})
                        seen_links.add(link_key)

    result = {"nodes": list(nodes.values()), "links": links}
    print(f"DEBUG: Final result for {producer_id}: {len(result['nodes'])} nodes, {len(result['links'])} links\n")
    return result

@ui.page('/')
async def index():
    with ui.column().classes('w-full items-center justify-center mt-8'):
        ui.label('Network Graph Analysis').classes('text-h2 mb-2')
        ui.label('Monitor, Analyze, and Visualize Spanner-backed Network Data').classes('text-h6 text-gray-500 mb-6')

    with ui.tabs().classes('w-full shadow-2 rounded-t-lg') as tabs:
        home_tab = ui.tab('Overview', icon='home')
        rca_tab = ui.tab('Network RCA', icon='analytics')
        blast_radius_tab = ui.tab('Blast Radius', icon='hub')

    with ui.tab_panels(tabs, value=home_tab).classes('w-full shadow-2 rounded-b-lg'):
        with ui.tab_panel(home_tab):
            with ui.column().classes('w-full items-center py-12'):
                ui.mermaid('''
                    graph LR
                        P((Producers)):::producer --> T1((Transit Nodes)):::transit
                        T1 --> T2((Transit Nodes)):::transit
                        T2 --> T1
                        T2 --> C((Consumers)):::consumer
                        classDef producer fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
                        classDef transit fill:#fff3e0,stroke:#e65100,stroke-width:2px;
                        classDef consumer fill:#f1f8e9,stroke:#33691e,stroke-width:2px;
                ''').classes('w-[500px] h-48')
                ui.label('Spanner Property Graph Analysis').classes('text-h5 mt-4 text-gray-600')

        with ui.tab_panel(rca_tab):
            ui.label('Network Root Cause Analysis').classes('text-h4 mb-4')
            async def refresh_rca():
                rca_container.clear()
                with rca_container:
                    ui.spinner()
                    def get_rca():
                        query = """
                        SELECT
                          TransitNode, TotalDownstream, OfflineDownstream,
                          ROUND( SAFE_DIVIDE(OfflineDownstream, TotalDownstream) * SAFE_DIVIDE(OfflineDownstream, 3.0), 4) AS SuspicionScore,
                          ROUND(SAFE_DIVIDE(OfflineDownstream, TotalDownstream), 2) AS DownstreamImpactRatio,
                          ROUND(SAFE_DIVIDE(OfflineDownstream, 3.0), 2) AS GlobalFaultCoverage
                        FROM (
                          SELECT
                            TransitNode, COUNT(ConsumerId) AS TotalDownstream,
                            COUNT(CASE WHEN ConsumerId IN ( SELECT NodeId FROM `Consumers` WHERE Status = 'DOWN') THEN 1 END) AS OfflineDownstream
                          FROM GRAPH_TABLE(
                                NetworkGraph MATCH(t:TransitNodes)-[:Connections_TT]->{0,10}(:TransitNodes)-[:Connections_TC]-> (c:`Consumers`)
                                COLUMNS(t.NodeId AS TransitNode, c.NodeId AS ConsumerId)
                          ) GROUP BY TransitNode)
                        WHERE OfflineDownstream > 0
                        ORDER BY SuspicionScore DESC LIMIT 15;
                        """
                        return query_spanner(query)
                    df_data = await asyncio.to_thread(get_rca)
                    rca_container.clear()
                    if not df_data:
                        ui.label('No issues detected.')
                    else:
                        ui.table(
                            columns=[{'name': k, 'label': k, 'field': k, 'sortable': True} for k in df_data[0].keys()],
                            rows=df_data,
                        ).classes('w-full rounded-lg overflow-hidden').props('flat bordered striped dense')

            rca_container = ui.column().classes('w-full')
            ui.button('Refresh RCA', icon='refresh', on_click=refresh_rca).classes('mt-4')
            ui.timer(0.1, refresh_rca, once=True)

        with ui.tab_panel(blast_radius_tab):
            ui.label('Producer Blast Radius').classes('text-h4 mb-4')
            producers = [r['NodeId'] for r in query_spanner("SELECT NodeId FROM Producers ORDER BY NodeId")]
            
            async def on_change(e):
                if not e.value: return
                n = ui.notification('Fetching blast radius data...', loading=True, timeout=None)
                try:
                    data = await asyncio.to_thread(get_blast_radius_data, e.value)
                    if not data['nodes']: ui.notify('No connections found.', type='warning')
                    await ui.run_javascript(f"window.renderGraph({json.dumps(data)})")
                except Exception as ex:
                    ui.notify(f"Error: {str(ex)}", type='negative')
                finally:
                    n.dismiss()

            ui.select(producers, label='Select Producer', on_change=on_change).classes('w-64')
            ui.html('<div id="graph" style="width: 100%; height: 700px; border: 1px solid #ddd;" class="mt-4"></div>')

# Global scripts for ForceGraph
ui.add_head_html('<script src="https://unpkg.com/force-graph"></script>', shared=True)
ui.add_body_html("""
<script>
let Graph;
window.renderGraph = function(data) {
    const el = document.getElementById('graph');
    if (!el || !data) return;
    if (!Graph) {
        Graph = ForceGraph()(el)
            .nodeId('id')
            .nodeAutoColorBy('group')
            .height(700)
            .nodeCanvasObject((node, ctx, globalScale) => {
                const label = node.name;
                const fontSize = 14/globalScale;
                ctx.font = `${fontSize}px Sans-Serif`;
                const textWidth = ctx.measureText(label).width;
                const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);
                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = node.color;
                ctx.fillText(label, node.x, node.y);
                node.__bckgDimensions = bckgDimensions;
            })
            .nodePointerAreaPaint((node, color, ctx) => {
                ctx.fillStyle = color;
                const bckgDimensions = node.__bckgDimensions;
                bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
            });
        Graph.d3Force('charge').strength(-200);
    }
    Graph.graphData(data);
    Graph.onEngineStop(() => Graph.zoomToFit(400, 0.8));
};
</script>
""", shared=True)

ui.run(title="Network Graph Analysis", port=8080)
