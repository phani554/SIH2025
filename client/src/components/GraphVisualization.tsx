import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Network, ZoomIn, ZoomOut, Download } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';

interface GraphNode {
  id: string;
  name: string;
  type: 'document' | 'department' | 'deadline' | 'person';
  properties?: Record<string, any>;
}

interface GraphLink {
  source: string;
  target: string;
  relationship: string;
  strength?: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface GraphVisualizationProps {
  data?: GraphData;
  isLoading?: boolean;
}

const NODE_COLORS = {
  document: '#6366F1',
  department: '#8B5CF6', 
  deadline: '#F59E0B',
  person: '#10B981'
};

export default function GraphVisualization({ data, isLoading = false }: GraphVisualizationProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Mock data for demonstration
  const mockData: GraphData = {
    nodes: [
      { id: '1', name: 'Financial Report Q4', type: 'document' },
      { id: '2', name: 'Finance Department', type: 'department' },
      { id: '3', name: 'Tax Filing Deadline', type: 'deadline' },
      { id: '4', name: 'John Smith (CFO)', type: 'person' },
      { id: '5', name: 'Budget Analysis', type: 'document' },
      { id: '6', name: 'Compliance Report', type: 'document' },
      { id: '7', name: 'Legal Department', type: 'department' },
      { id: '8', name: 'Contract Review', type: 'deadline' }
    ],
    links: [
      { source: '1', target: '2', relationship: 'assigned_to' },
      { source: '1', target: '3', relationship: 'creates_deadline' },
      { source: '2', target: '4', relationship: 'managed_by' },
      { source: '5', target: '2', relationship: 'assigned_to' },
      { source: '6', target: '7', relationship: 'assigned_to' },
      { source: '6', target: '8', relationship: 'creates_deadline' },
      { source: '4', target: '3', relationship: 'responsible_for' }
    ]
  };

  const graphData = data || mockData;

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
  };

  const handleExport = () => {
    console.log('Exporting graph data:', graphData);
    // In a real implementation, this would export the graph as JSON or image
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button 
          variant="outline" 
          className="flex items-center gap-2"
          data-testid="button-open-graph"
        >
          <Network className="w-4 h-4" />
          View Graph Visualization
        </Button>
      </DialogTrigger>
      
      <DialogContent className="max-w-4xl h-[80vh]">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle data-testid="graph-title">Document Relationship Graph</DialogTitle>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" data-testid="button-zoom-in">
                <ZoomIn className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="icon" data-testid="button-zoom-out">
                <ZoomOut className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={handleExport}
                data-testid="button-export-graph"
              >
                <Download className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="flex h-full gap-4">
          {/* Graph Visualization */}
          <div className="flex-1 border rounded-lg overflow-hidden" data-testid="graph-container">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center space-y-3">
                  <Network className="w-8 h-8 mx-auto text-primary animate-pulse" />
                  <p className="text-sm text-muted-foreground">Loading graph data...</p>
                </div>
              </div>
            ) : (
              <ForceGraph2D
                graphData={graphData}
                nodeAutoColorBy="type"
                nodeColor={(node: any) => NODE_COLORS[node.type as keyof typeof NODE_COLORS]}
                nodeLabel={(node: any) => `${node.name} (${node.type})`}
                linkLabel={(link: any) => link.relationship}
                onNodeClick={handleNodeClick}
                nodeRelSize={8}
                linkWidth={2}
                linkColor="#999"
                backgroundColor="#ffffff"
                width={600}
                height={400}
              />
            )}
          </div>

          {/* Node Details Panel */}
          <div className="w-64 space-y-4">
            <div>
              <h4 className="font-medium mb-2">Legend</h4>
              <div className="space-y-2">
                {Object.entries(NODE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2 text-sm">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: color }}
                    />
                    <span className="capitalize">{type.replace('_', ' ')}</span>
                  </div>
                ))}
              </div>
            </div>

            {selectedNode && (
              <div>
                <h4 className="font-medium mb-2">Node Details</h4>
                <div className="space-y-2">
                  <div className="p-3 border rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <div 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: NODE_COLORS[selectedNode.type as keyof typeof NODE_COLORS] }}
                      />
                      <Badge variant="secondary">{selectedNode.type}</Badge>
                    </div>
                    <h5 className="font-medium text-sm" data-testid="selected-node-name">
                      {selectedNode.name}
                    </h5>
                    {selectedNode.properties && (
                      <div className="mt-2 text-xs text-muted-foreground">
                        {Object.entries(selectedNode.properties).map(([key, value]) => (
                          <div key={key}>
                            <span className="font-medium">{key}:</span> {value}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div>
              <h4 className="font-medium mb-2">Graph Stats</h4>
              <div className="text-sm text-muted-foreground space-y-1">
                <div>Nodes: {graphData.nodes.length}</div>
                <div>Relationships: {graphData.links.length}</div>
                <div>Types: {new Set(graphData.nodes.map(n => n.type)).size}</div>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}