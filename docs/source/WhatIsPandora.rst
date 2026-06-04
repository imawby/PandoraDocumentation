What Is Pandora?
================

Pandora is a multi-algorithm reconstruction framework used to solve pattern recognition problems in high energy physics. It has over 100 different algorithms that can be applied in a range of orders to allow users to create custom reconstruction for individual needs. Each step is small, but making sure every one is correct before moving onto the next allows us to get to the correct answer with minimal opportunity for mistakes. It also means we can develop certain areas (e.g. vertex positioning) and slot them right back in once they've been improved.

As it is a dependency free library, Pandora has been used for reconstrction in a number of liquid argon detector particle physics experiments, namely DUNE (Near and Far Detectors), SBND, MicroBooNE, ICARUS, and some linear collider experiments (ILC, CLIC, FCC-ee). We make careful use of both traditional clustering as well as novel AI/ML approaches.

The Event Data Model uses classes to represent the input building blocks (CaloHits, Tracks, MC Particles) and then uses these to created higher-level structures (Clusters, Verticies, Particles). That is to say, it takes in fairly basic data and outputs reconstructed particles to be used for analysis!

.. csv-table::
   :header: "Name", "Description"
   :widths: 15, 30

   "CaloHits", "Primary building block, defining a position and extent in space (or time), with an associated intensity or energy measurement and detector location details."
   "Tracks", "Represents a continuous trajectory of well-defined space-points, with helix parameterisation. Track parent-child and sibling relationships supported."
   "MCParticles", "For development/validation: provide details of true pattern-recognition solution. Support parent-child links and can be associated to CaloHits and Tracks."
   "Clusters", "Collection of CaloHits and main working horse for algorithms (which create, merge, split Clusters). Provides some derived properties of CaloHit collection."
   "Vertex", "The identification and classification of a specific point in space, typically used to flag positions of particle creation or decay."
   "Particle", "Container of Clusters, Tracks and Vertices, together with metadata describing e.g. particle id. Ultimate Pandora output and can represent a hierarchy."


Who We Are
----------

PandoraPFA (Particle Flow Algorithm) was orginally created at the University of Cambridge in 2005 by Mark Thompson. John Marshall picked up the project soon after (2009), and things have only grown from there. There is now a stable team based in the UK who are supported by a named, fully funded, and managed STFC project through to 2028. We are now also becoming more international, with groups in the USA and Italy having joined the project.

Please find below the names of Pandora collaborators who work on a number of experiments. 

- DUNE FD = Dom Brailsford, John Marshall, Andy Chappell, Alexandra Moor, Alex Wilkinson, Isobel Mawby, Leigh Whitehead, Rhiannon Smith-Jones
- DUNE ND = Ryan Cross, Maria Brigida Brunetti, Bruce Howard
- protoDUNE = Leigh Whitehead, Dom Brailsford, John Marshall, Andy Chappell, Alexandra Moor, Alex Wilkinson, Isobel Mawby, Rhiannon Smith-Jones
- SBND = Alex Wilkinson, Andy Chappell, Alexandra Moor, John Marshall, Dom Brailsford
- ICARUS = Alice Campani, Bruce Howard, Mattia Sotgia, Riccardo Triozzi
- MicroBooNE = Isobel Mawby, Andy Chappell

Institutions contributing to the project: University of Cambridge (UK), University of Warwick (UK), Lancaster University (UK), University of Sheffield (UK), University of Kansas (USA), York University (Canada), Fermilab, INFN Genova (Italy), Università degli Studi di Genova (Italy), INFN Padova (Italy), Università di Padova (Italy).



Standard Event Reconstruction Algorithms
----------------------------------------

Chains are lists of algorithms run consecutively in order to tackle a particular reconstruction problem, and there are a huge variety of ways the individual algorithms can be combined to make them. Most detectors have a standard specialised chain to achive optimum performance for their particular setup. Often a chain for tagging cosmic rays (which focuses on finding parent tracks) is applied first and followed by a chain for identifying neutrinos (which focuses on finding the neutrino vertex and resulting charged particles).

Most of these chains will follow a common series of steps at the most basic level for the event reconstruction. A simple summary is given in the table below.

.. csv-table::
   :header: "Stage", "Name", "Description"
   :widths: 10, 15, 30

   "1", "2D Clustering", "In each 2D view, hits are grouped together to form clusters using topological information."
   "2", "3D Vertex Positioning", "2D clusters are compared to identify the most likely 3D vertex."
   "3", "Track Reconstruction", "2D clusters are collected to form 3D tracks. Such 3D tracks are known as Particle-Flow Objects (PFOs)."
   "4", "Delta Ray Formation", "2D clusters not assigned to a PFO are dissolved and reassigned. Only run when looking for cosmic rays."
   "5", "Shower Reconstruction", "Each PFO is assessed and designated as track- or shower-like. Shower-like clusters are then dissolved and reclustered by specialised algorithms, eventually forming shower PFOs. Only run for a neutrino chain."
   "6", "3D Space Point Creation", "3D space points for the PFO trajectories are calculated from 2D hits."
   "7", "Event Building", "Particles are sorted into a hierarchy. The neutrino flavour that triggered the event is also identified."
