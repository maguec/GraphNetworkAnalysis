import os
import pandas as pd
from dotenv import load_dotenv
from google.cloud import spanner

# Load environment variables
load_dotenv(override=True)
GOOGLE_PROJECT = os.getenv("GOOGLE_PROJECT")
GOOGLE_SPANNER_INSTANCE = os.getenv("GOOGLE_SPANNER_INSTANCE")
GOOGLE_SPANNER_DATABASE = os.getenv("GOOGLE_SPANNER_DATABASE")

# Explicit check to catch the error early
for var_name, value in {
    "GOOGLE_PROJECT": GOOGLE_PROJECT,
    "SPANNER_INSTANCE": GOOGLE_SPANNER_INSTANCE,
    "SPANNER_DATABASE": GOOGLE_SPANNER_DATABASE,
}.items():
    if value is None:
        raise ValueError(
            f"Environment variable {var_name} is missing! Check your .env file."
        )


def setup_spanner_graph():
    client = spanner.Client(project=GOOGLE_PROJECT, disable_builtin_metrics=True)
    instance = client.instance(GOOGLE_SPANNER_INSTANCE)
    database = instance.database(GOOGLE_SPANNER_DATABASE)

    print(f"Recreating Graph and Tables in {GOOGLE_SPANNER_DATABASE}...")

    # 1. Clean up existing Graph and Tables
    # Order matters due to foreign key constraints and graph dependencies
    ddl_statements = [
        "DROP PROPERTY GRAPH IF EXISTS NetworkGraph",
        "DROP TABLE IF EXISTS Connections_TC",
        "DROP TABLE IF EXISTS Connections_TT",
        "DROP TABLE IF EXISTS Connections_PT",
        "DROP TABLE IF EXISTS Consumers",
        "DROP TABLE IF EXISTS TransitNodes",
        "DROP TABLE IF EXISTS Producers",
    ]

    # 2. Define Node Tables
    ddl_statements.extend(
        [
            """CREATE TABLE Producers (
            NodeId STRING(36) NOT NULL,
            NodeType STRING(MAX),
            Status STRING(MAX)
        ) PRIMARY KEY (NodeId)""",
            """CREATE TABLE TransitNodes (
            NodeId STRING(36) NOT NULL,
            NodeType STRING(MAX),
            Status STRING(MAX)
        ) PRIMARY KEY (NodeId)""",
            """CREATE TABLE Consumers (
            NodeId STRING(36) NOT NULL,
            NodeType STRING(MAX),
            Status STRING(MAX)
        ) PRIMARY KEY (NodeId)""",
        ]
    )

    # 3. Define Edge Tables
    ddl_statements.extend(
        [
            """CREATE TABLE Connections_PT (
            FromNodeId STRING(36) NOT NULL,
            ToNodeId STRING(36) NOT NULL,
            FOREIGN KEY (FromNodeId) REFERENCES Producers (NodeId),
            FOREIGN KEY (ToNodeId) REFERENCES TransitNodes (NodeId)
        ) PRIMARY KEY (FromNodeId, ToNodeId)""",
            """CREATE TABLE Connections_TT (
            FromNodeId STRING(36) NOT NULL,
            ToNodeId STRING(36) NOT NULL,
            FOREIGN KEY (FromNodeId) REFERENCES TransitNodes (NodeId),
            FOREIGN KEY (ToNodeId) REFERENCES TransitNodes (NodeId)
        ) PRIMARY KEY (FromNodeId, ToNodeId)""",
            """CREATE TABLE Connections_TC (
            FromNodeId STRING(36) NOT NULL,
            ToNodeId STRING(36) NOT NULL,
            FOREIGN KEY (FromNodeId) REFERENCES TransitNodes (NodeId),
            FOREIGN KEY (ToNodeId) REFERENCES Consumers (NodeId)
        ) PRIMARY KEY (FromNodeId, ToNodeId)""",
        ]
    )

    # 4. Define Property Graph
    ddl_statements.append("""
        CREATE PROPERTY GRAPH NetworkGraph
        NODE TABLES (Producers, TransitNodes, Consumers)
        EDGE TABLES (
            Connections_PT SOURCE KEY (FromNodeId) REFERENCES Producers DESTINATION KEY (ToNodeId) REFERENCES TransitNodes,
            Connections_TT SOURCE KEY (FromNodeId) REFERENCES TransitNodes DESTINATION KEY (ToNodeId) REFERENCES TransitNodes,
            Connections_TC SOURCE KEY (FromNodeId) REFERENCES TransitNodes DESTINATION KEY (ToNodeId) REFERENCES Consumers
        )
    """)

    operation = database.update_ddl(ddl_statements)
    operation.result()
    print("Schema created successfully.")

    # 5. Load Data
    def insert_csv_to_spanner(table_name, csv_file):
        df = pd.read_csv(csv_file)
        columns = df.columns.tolist()
        data = [tuple(x) for x in df.values]

        with database.batch() as batch:
            batch.insert(table_name, columns=columns, values=data)
        print(f"Loaded {len(df)} rows into {table_name}")

    insert_csv_to_spanner("Producers", "data/producers.csv")
    insert_csv_to_spanner("TransitNodes", "data/transit_nodes.csv")
    insert_csv_to_spanner("Consumers", "data/consumers.csv")
    insert_csv_to_spanner("Connections_PT", "data/edges_producers_to_transit.csv")
    insert_csv_to_spanner("Connections_TT", "data/edges_transit_to_transit.csv")
    insert_csv_to_spanner("Connections_TC", "data/edges_transit_to_consumers.csv")


if __name__ == "__main__":
    confirm = input("This will DROP and recreate your tables. Proceed? (y/n): ")
    if confirm.lower() == "y":
        setup_spanner_graph()
    else:
        print("Aborted.")
