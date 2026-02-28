(function () {
    'use strict';

    /**
     * Parse a Newick-format string into a tree object.
     * Returns nested objects with { name, length, children } properties.
     */
    function parseNewick(s) {
        var ancestors = [];
        var tree = {};
        var tokens = s.split(/\s*(;|\(|\)|,|:)\s*/);
        for (var i = 0; i < tokens.length; i++) {
            var token = tokens[i];
            switch (token) {
                case '(': {
                    var child = {};
                    if (!tree.children) tree.children = [];
                    tree.children.push(child);
                    ancestors.push(tree);
                    tree = child;
                    break;
                }
                case ',': {
                    var sibling = {};
                    ancestors[ancestors.length - 1].children.push(sibling);
                    tree = sibling;
                    break;
                }
                case ')':
                    tree = ancestors.pop();
                    break;
                case ':':
                    break;
                default: {
                    if (token.length === 0) break;
                    var prev = tokens[i - 1];
                    if (prev === ':') {
                        tree.length = parseFloat(token);
                    } else {
                        tree.name = token;
                    }
                    break;
                }
            }
        }
        return tree;
    }

    /**
     * Render a phylogenetic tree from a Newick string into the given container element.
     * Requires D3.js v7 to be loaded globally.
     */
    function renderTree(container, newickString) {
        container.innerHTML = '';

        var parsed;
        try {
            parsed = parseNewick(newickString.trim().replace(/\s*;+\s*$/, ''));
        } catch (e) {
            container.innerHTML = '<p style="color:#721c24;padding:15px;">Failed to parse tree: ' + e.message + '</p>';
            return;
        }

        var width = container.clientWidth || 800;
        var height = 500;
        var ml = 50, mr = 180, mt = 20, mb = 20;

        var svg = d3.select(container)
            .append('svg')
            .attr('width', width)
            .attr('height', height)
            .style('display', 'block')
            .style('background', '#fff');

        var gRoot = svg.append('g');

        svg.call(
            d3.zoom()
                .scaleExtent([0.1, 10])
                .on('zoom', function (event) {
                    gRoot.attr('transform', event.transform);
                })
        );

        var g = gRoot.append('g')
            .attr('transform', 'translate(' + ml + ',' + mt + ')');

        var root = d3.hierarchy(parsed, function (d) { return d.children; });
        d3.cluster().size([height - mt - mb, width - ml - mr])(root);

        // Links — right-angle elbows (standard phylogram style)
        g.selectAll('path.tree-link')
            .data(root.descendants().slice(1))
            .join('path')
            .attr('class', 'tree-link')
            .attr('fill', 'none')
            .attr('stroke', '#aaa')
            .attr('stroke-width', 1.5)
            .attr('d', function (d) {
                return 'M' + d.y + ',' + d.x
                    + 'H' + d.parent.y
                    + 'V' + d.parent.x;
            });

        // Nodes
        var node = g.selectAll('g.tree-node')
            .data(root.descendants())
            .join('g')
            .attr('class', 'tree-node')
            .attr('transform', function (d) {
                return 'translate(' + d.y + ',' + d.x + ')';
            });

        node.append('circle')
            .attr('r', function (d) { return d.children ? 3 : 4.5; })
            .attr('fill', function (d) { return d.children ? '#777' : '#5e9e8b'; })
            .attr('stroke', '#fff')
            .attr('stroke-width', 1);

        // Leaf labels
        node.filter(function (d) { return !d.children; })
            .append('text')
            .attr('x', 9)
            .attr('dy', '0.32em')
            .style('font-size', '12px')
            .style('font-family', 'monospace, "Courier New"')
            .style('fill', '#212529')
            .attr('stroke', 'white')
            .attr('stroke-width', 3)
            .attr('stroke-linejoin', 'round')
            .style('paint-order', 'stroke fill')
            .text(function (d) { return d.data.name || ''; });

        // Internal node labels (posterior/support values)
        node.filter(function (d) { return d.children && d.data.name; })
            .append('text')
            .attr('x', 4)
            .attr('dy', '1.2em')
            .style('font-size', '11px')
            .style('font-family', 'monospace, "Courier New"')
            .style('fill', '#c0392b')
            .attr('stroke', 'white')
            .attr('stroke-width', 3)
            .attr('stroke-linejoin', 'round')
            .style('paint-order', 'stroke fill')
            .text(function (d) { return d.data.name; });

        // Branch length labels — positioned below the horizontal branch segment
        g.selectAll('text.branch-len')
            .data(root.descendants().filter(function (d) {
                return d.depth > 0 && d.data.length !== undefined;
            }))
            .join('text')
            .attr('class', 'branch-len')
            .attr('x', function (d) { return (d.y + d.parent.y) / 2; })
            .attr('y', function (d) { return d.x + 11; })
            .attr('text-anchor', 'middle')
            .style('font-size', '10px')
            .style('fill', '#555')
            .attr('stroke', 'white')
            .attr('stroke-width', 3)
            .attr('stroke-linejoin', 'round')
            .style('paint-order', 'stroke fill')
            .text(function (d) {
                var l = d.data.length;
                if (l === 0) return '0';
                return l < 0.001 ? l.toExponential(1) : l.toFixed(3);
            });

        // Scroll/drag hint
        d3.select(container)
            .append('div')
            .style('font-size', '10px')
            .style('color', '#aaa')
            .style('text-align', 'right')
            .style('padding', '2px 6px')
            .text('Scroll to zoom · Drag to pan');
    }

    function renderIfVisible(container) {
        if (container.hasAttribute('data-tree-rendered')) return;
        var newick = container.getAttribute('data-newick');
        if (newick && newick.trim().length > 0) {
            container.setAttribute('data-tree-rendered', 'true');
            renderTree(container, newick);
        }
    }

    function initTrees() {
        if (typeof d3 === 'undefined') return;
        // Only render containers that are currently visible
        document.querySelectorAll('.tree-container:not([data-tree-rendered])').forEach(function (container) {
            if (container.style.display !== 'none') {
                renderIfVisible(container);
            }
        });
    }

    // Toggle button click handler
    document.addEventListener('click', function (e) {
        if (!e.target.classList.contains('tree-toggle-btn')) return;
        var section = e.target.closest('.tree-section');
        if (!section) return;
        var container = section.querySelector('.tree-container');
        if (!container) return;

        var isHidden = container.style.display === 'none';
        container.style.display = isHidden ? 'block' : 'none';
        e.target.textContent = isHidden ? 'Hide Tree' : 'Show Tree';

        // Lazy-render on first show
        if (isHidden) renderIfVisible(container);
    });

    // Watch for Shiny re-rendering tree containers into DOM
    var observer = new MutationObserver(function (mutations) {
        for (var m of mutations) {
            if (m.addedNodes.length > 0) {
                initTrees();
                break;
            }
        }
    });

    function setup() {
        observer.observe(document.body, { childList: true, subtree: true });
        initTrees();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();
