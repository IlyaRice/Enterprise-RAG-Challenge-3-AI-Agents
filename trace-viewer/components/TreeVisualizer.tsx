import React, { useEffect, useRef, useState, useMemo } from "react";
import * as d3 from "d3";
import { TraceEvent } from "../types";
import { NODE_COLORS } from "../constants";
import { filterAgentSteps, buildValidatorLookup } from "../utils";

interface TreeVisualizerProps {
  data: TraceEvent[];
  onSelectNode: (node: TraceEvent) => void;
  selectedNodeId: string | null;
  onBackgroundClick?: () => void;
}

interface PositionedNode {
  x: number;
  y: number;
  data: TraceEvent;
}

interface TreeLink {
  source: PositionedNode;
  target: PositionedNode;
}

/**
 * Layout configuration for diagonal cascade with alternating angles
 */
const LAYOUT_CONFIG = {
  // Spacing for main timeline (depth 0)
  mainTimelineSpacing: 200,
  // Spacing for sub-branches (depth 1+)
  branchSpacing: 90,
  
  // Get step size based on depth
  getStepSize: (depth: number): number => {
    const normalizedDepth = depth <= 0 ? 0 : depth;
    return normalizedDepth === 0 
      ? LAYOUT_CONFIG.mainTimelineSpacing 
      : LAYOUT_CONFIG.branchSpacing;
  },
  
  // Angles for each depth level (in radians)
  // depth 0 (and -1): horizontal (0°)
  // depth 1: 70° diagonal (nearly vertical, slight right tilt)
  // depth 2: 110° diagonal (vertically mirrored from depth 1, down-left)
  getAngle: (depth: number): number => {
    const normalizedDepth = depth <= 0 ? 0 : depth;
    if (normalizedDepth === 0) return 0; // horizontal (0°)
    if (normalizedDepth % 2 === 1) return (70 * Math.PI) / 180; // 70° for odd depths (down-right)
    return (110 * Math.PI) / 180; // 110° for even depths (mirrored, down-left)
  },
};

/**
 * Build layout with:
 * - Edges based on prev_sibling_node_id (sequential) or parent_node_id (spawn)
 * - Alignment based on depth field with alternating diagonal angles
 */
function buildDiagonalCascadeLayout(
  data: TraceEvent[]
): { nodes: PositionedNode[]; links: TreeLink[] } {
  if (data.length === 0) return { nodes: [], links: [] };

  // Build lookup maps
  const nodeMap = new Map<string, TraceEvent>();
  const positionMap = new Map<string, PositionedNode>();

  for (const node of data) {
    nodeMap.set(node.node_id, node);
  }

  // Sort nodes by their node_id to process in order
  const sortedNodes = [...data].sort((a, b) =>
    a.node_id.localeCompare(b.node_id, undefined, { numeric: true })
  );

  const links: TreeLink[] = [];

  // Track positions for each depth level to handle sequential siblings
  const depthCounters = new Map<string, number>();

  // Process each node
  for (const node of sortedNodes) {
    let x: number;
    let y: number;

    // Normalize depth: treat -1 as 0 (same horizontal line)
    const normalizedDepth = node.depth <= 0 ? 0 : node.depth;
    const angle = LAYOUT_CONFIG.getAngle(node.depth);
    const stepSize = LAYOUT_CONFIG.getStepSize(node.depth);

    if (node.prev_sibling_node_id !== null) {
      // Sequential connection: position relative to previous sibling
      const prevSibling = positionMap.get(node.prev_sibling_node_id);
      if (prevSibling) {
        // Move along the angle direction from sibling
        x = prevSibling.x + Math.cos(angle) * stepSize;
        y = prevSibling.y + Math.sin(angle) * stepSize;

        // Create edge from prev_sibling to this node
        links.push({
          source: prevSibling,
          target: { x, y, data: node }, // Will be updated below
        });
      } else {
        // Fallback if sibling not found
        x = normalizedDepth * stepSize;
        y = 0;
      }
    } else if (node.parent_node_id !== null) {
      // Spawn connection: new branch from parent
      const parent = positionMap.get(node.parent_node_id);
      if (parent) {
        // Start a new branch from the parent, offset in the new angle direction
        x = parent.x + Math.cos(angle) * stepSize;
        y = parent.y + Math.sin(angle) * stepSize;

        // Create edge from parent to this node
        links.push({
          source: parent,
          target: { x, y, data: node }, // Will be updated below
        });
      } else {
        // Fallback if parent not found
        x = normalizedDepth * stepSize;
        y = 0;
      }
    } else {
      // Root node (no parent, no sibling)
      x = 0;
      y = 0;
    }

    const positioned: PositionedNode = { x, y, data: node };
    positionMap.set(node.node_id, positioned);

    // Update link targets with the actual positioned node reference
    const lastLink = links[links.length - 1];
    if (lastLink && lastLink.target.data.node_id === node.node_id) {
      lastLink.target = positioned;
    }
  }

  return {
    nodes: Array.from(positionMap.values()),
    links,
  };
}

const TreeVisualizer: React.FC<TreeVisualizerProps> = ({
  data,
  onSelectNode,
  selectedNodeId,
  onBackgroundClick,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  
  // UPDATED: Add hover state with timeout ref for delayed hiding
  const [hoveredNode, setHoveredNode] = useState<{ node: TraceEvent; x: number; y: number } | null>(null);
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isOverTooltipRef = useRef<boolean>(false);
  const isOverNodeRef = useRef<boolean>(false);

  // Helper to clear any pending hide timeout
  const clearHideTimeout = () => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };

  // Helper to schedule hiding the tooltip with a small delay
  const scheduleHide = () => {
    clearHideTimeout();
    hideTimeoutRef.current = setTimeout(() => {
      // Only hide if mouse is not over node or tooltip
      if (!isOverTooltipRef.current && !isOverNodeRef.current) {
        setHoveredNode(null);
      }
    }, 500); // 500ms delay to allow moving to tooltip
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => clearHideTimeout();
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (wrapperRef.current) {
        setDimensions({
          width: wrapperRef.current.clientWidth,
          height: wrapperRef.current.clientHeight,
        });
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const nodeRadius = 18;

  // Filter out validator events and build validator lookup
  const filteredData = useMemo(() => filterAgentSteps(data), [data]);
  const validatorLookup = useMemo(() => buildValidatorLookup(data), [data]);

  // Compute layout
  const { nodes, links } = useMemo(
    () => buildDiagonalCascadeLayout(filteredData),
    [filteredData]
  );

  useEffect(() => {
    if (nodes.length === 0 || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Add background click handler BEFORE appending g
    if (onBackgroundClick) {
      svg.on("click", (event: MouseEvent) => {
        // Only fires if click wasn't on a node (they use stopPropagation)
        onBackgroundClick();
      });
    }

    const g = svg.append("g");

    // Zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Calculate bounds for centering
    const xExtent = d3.extent(nodes, (n: PositionedNode) => n.x) as [number, number];
    const yExtent = d3.extent(nodes, (n: PositionedNode) => n.y) as [number, number];
    const treeWidth = (xExtent[1] - xExtent[0]) || 1;
    const treeHeight = (yExtent[1] - yExtent[0]) || 1;

    // Center the visualization
    const padding = 150;
    const availableWidth = dimensions.width - 2 * padding;
    const availableHeight = dimensions.height - 2 * padding;
    const scaleX = availableWidth / treeWidth;
    const scaleY = availableHeight / treeHeight;
    const scale = Math.min(scaleX, scaleY, 1);

    // Offset to center the tree
    const offsetX = padding - xExtent[0] * scale + (availableWidth - treeWidth * scale) / 2;
    const offsetY = padding - yExtent[0] * scale + (availableHeight - treeHeight * scale) / 2;

    const initialTransform = d3.zoomIdentity
      .translate(offsetX, offsetY)
      .scale(scale);
    svg.call(zoom.transform, initialTransform);

    // Render links
    g.selectAll<SVGPathElement, TreeLink>(".link")
      .data(links)
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", "#525252")
      .attr("stroke-width", 2)
      .attr("opacity", 0.6)
      .attr("d", (d: TreeLink) => {
        const sx = d.source.x;
        const sy = d.source.y;
        const tx = d.target.x;
        const ty = d.target.y;

        // For horizontal links, use horizontal curve
        // For diagonal links, use a slight curve
        if (Math.abs(sy - ty) < 1) {
          // Horizontal: simple line or slight curve
          return `M ${sx} ${sy} L ${tx} ${ty}`;
        } else {
          // Diagonal: bezier curve
          const midX = (sx + tx) / 2;
          return `M ${sx} ${sy} Q ${midX} ${sy}, ${tx} ${ty}`;
        }
      });

    // Render nodes
    const nodeGroup = g
      .selectAll<SVGGElement, PositionedNode>(".node")
      .data(nodes)
      .enter()
      .append("g")
      .attr("class", "node cursor-pointer")
      .attr("transform", (d: PositionedNode) => `translate(${d.x},${d.y})`)
      .on("click", (event: MouseEvent, d: PositionedNode) => {
        event.stopPropagation();
        onSelectNode(d.data);
      })
      // UPDATED: Hover handlers with delayed hide
      .on("mouseenter", (event: MouseEvent, d: PositionedNode) => {
        clearHideTimeout(); // Cancel any pending hide
        isOverNodeRef.current = true;
        // Store absolute screen coordinates for fixed positioning
        setHoveredNode({
          node: d.data,
          x: event.clientX,
          y: event.clientY,
        });
      })
      .on("mouseleave", () => {
        isOverNodeRef.current = false;
        scheduleHide(); // Delay hide to allow moving to tooltip
      });

    // Node circles
    nodeGroup
      .append("circle")
      .attr("r", nodeRadius)
      .attr("fill", (d: PositionedNode) => NODE_COLORS[d.data.context] || "#cbd5e1")
      .attr("stroke", (d: PositionedNode) =>
        d.data.node_id === selectedNodeId ? "#ffffff" : "none"
      )
      .attr("stroke-width", (d: PositionedNode) => (d.data.node_id === selectedNodeId ? 3 : 0))
      .attr("class", "transition-all duration-200 hover:brightness-110")
      .style("filter", "drop-shadow(0px 0px 8px rgba(0,0,0,0.5))");

    // Selection glow ring
    nodeGroup
      .filter((d: PositionedNode) => d.data.node_id === selectedNodeId)
      .append("circle")
      .attr("r", nodeRadius + 6)
      .attr("fill", "none")
      .attr("stroke", "#ffffff")
      .attr("stroke-opacity", 0.3)
      .attr("stroke-width", 1);

    // Context labels
    nodeGroup
      .append("text")
      .attr("dy", nodeRadius + 15)
      .attr("text-anchor", "middle")
      .attr("fill", "#e5e5e5")
      .style("font-size", "12px")
      .style("font-weight", "500")
      .style("pointer-events", "none")
      .text((d: PositionedNode) => d.data.context);

    // Timing labels
    nodeGroup
      .append("text")
      .attr("dy", nodeRadius + 28)
      .attr("text-anchor", "middle")
      .attr("fill", "#737373")
      .style("font-size", "10px")
      .style("pointer-events", "none")
      .text((d: PositionedNode) => `${d.data.timing.toFixed(2)}s`);

    // Validation status emoji overlay
    nodeGroup
      .filter((d: PositionedNode) => validatorLookup.has(d.data.node_id))
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em") // Vertically center the emoji
      .style("font-size", "16px")
      .style("pointer-events", "none")
      .text((d: PositionedNode) => {
        const validator = validatorLookup.get(d.data.node_id);
        return validator?.validation_passed ? "✅" : "❌";
      });

  }, [nodes, links, dimensions, onSelectNode, selectedNodeId, nodeRadius, onBackgroundClick, validatorLookup]);

  return (
    <div
      ref={wrapperRef}
      className="w-full h-full bg-black relative overflow-hidden"
    >
      <svg ref={svgRef} className="w-full h-full block" />
      
      {/* UPDATED: Hover tooltip with fixed positioning to overlay on top of everything */}
      {hoveredNode && (() => {
        const sidebarWidth = selectedNodeId ? 500 : 0;
        const availableWidth = window.innerWidth - sidebarWidth;
        const shouldFlipLeft = hoveredNode.x > availableWidth / 2;
        
        return (
          <div
            className="fixed z-[100] bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl p-3 max-w-2xl pointer-events-auto"
            style={{
              left: shouldFlipLeft ? undefined : hoveredNode.x + 10,
              right: shouldFlipLeft ? window.innerWidth - hoveredNode.x + 10 : undefined,
              top: hoveredNode.y - 10,
            }}
            onMouseEnter={() => {
              clearHideTimeout();
              isOverTooltipRef.current = true;
            }}
            onMouseLeave={() => {
              isOverTooltipRef.current = false;
              scheduleHide();
            }}
          >
            <div className="text-xs font-bold text-neutral-400 uppercase mb-2">
              Decision Output
            </div>
            <pre className="font-mono text-xs bg-neutral-950 p-2 rounded border border-neutral-800 text-neutral-300 overflow-auto max-h-96 whitespace-pre-wrap break-words">
              {JSON.stringify(hoveredNode.node.output, null, 2)}
            </pre>
          </div>
        );
      })()}

      <div className="absolute bottom-4 left-4 bg-neutral-900/80 border border-neutral-800 p-2 rounded shadow-lg text-xs text-neutral-400 pointer-events-none backdrop-blur-sm">
        Scroll to Zoom • Drag to Pan • Click Nodes
      </div>
    </div>
  );
};

export default TreeVisualizer;
