# Atlas × JLC: new physical products that traditional CAD doesn't make easy

The big opportunity isn't simply prompt → mesh → 3D print. Conventional CAD can already make arbitrary printable shapes, given enough modelling work.

What Atlas changes is the starting material. You can feed it photographs, videos, imagined scenes and places that don't have engineering drawings, then generate a spatial representation that can be adapted into a physical object.

That creates a new class of products:

Memories, atmospheres and imaginary worlds made physical.

World Labs now supports world generation from images, video and text, with Gaussian splat and mesh exports. JLC3DP offers full-colour resin printing with a published starting price of $5 per part, recommended walls above 1 mm, and up to 380 × 330 × 230 mm build size for that material. Actual quotes depend heavily on geometry and size.

## 1. The ideas I'd be most excited to prototype

1. Memory Fossils — preserve a real place

Upload a few photographs of Grandma's kitchen, your childhood bedroom, the café where you met, or your first apartment.

Atlas reconstructs the visual scene. OddHobb turns it into a miniature diorama or build-it-yourself kit.

New advantage: The customer needn't supply floorplans, architectural measurements or a 3D model. The scene itself is the design reference.

Best for: OddHobb emotional gifts · High personalisation

2. A Street You Remember

A slice of someone's hometown: their childhood shop, favourite pub, restaurant, street corner or university building.

Manufacture a miniature architectural facade mounted on a plinth, with a QR-linked explorable reconstruction.

New advantage: A handful of photographs can supply architectural style and scene context without someone hand-modelling every sign, window and style.

3. Imagination Houses

"Make a tiny home for Jenny, a witch who lives in an overgrown mushroom cottage and collects broken clocks."

Atlas establishes the world visually, then our pipeline extracts a manufacturable exterior shell and creates component openings for lights and sound.

New advantage: Customers can commission imaginary architectures without knowing architectural vocabulary or modelling software.

Best for: Pogtown agent homes · Living fairy houses

4. Fictional Places as Collectibles

Instead of printing a character, print the location that matters to them: their workshop, tavern, comedy club, secret laboratory or bedroom.

Atlas can provide a visually consistent fictional location, while OddHobb converts a selected portion into a printable miniature.

New advantage: The design starts as an inhabitable world, not just a decorative object. A Pogtown character can exist inside the same environment digitally.

5. Personalised Book Nooks From Stories

A public-domain passage or a customer's own story becomes a spatial scene, then a custom book nook.

Imagine building the library in a favourite fairy tale, or a miniature alchemist's study based on a historical grimoire.

New advantage: Text can create a spatial design language first. The manufacturing compiler then reduces it into a feasible kit.

Best for: OddHobb · Ochema · Literary gifts

These five are variations of one reusable business: scene-to-object manufacturing.

The hard, valuable work is reconstructing useful geometry, determining what should be printed separately, preserving recognisable details and packaging a satisfying physical result.

## 2. More experimental products that could become new categories

These are especially interesting because they're difficult to design manually at scale, rather than impossible to make with CAD.

6. Spatial Photographs

Imagine a photograph that physically extends out of its frame. Buildings have real depth, people have physical volume, and an entire moment becomes a shallow miniature sculpture.

Atlas helps infer scene depth and unseen geometry. OddHobb compresses the reconstructed scene into a printable 2.5D relief.

Commercial angle: Weddings, travel, anniversaries, family memories.

7. Splat Cubes — volumetric photographs

This is particularly exciting because somebody has already demonstrated the underlying physical technique.

A recent project called SplatCubes converts 3D Gaussian-splat data into multi-material resin sculptures suspended inside clear material.

Imagine a physical 3D photograph of a forest, childhood room, or tiny moment in time.

This would require a specialist multi-material printing partner; JLC's ordinary full-colour resin service is not a verified equivalent.

8. Slice a World

Take any reconstructed environment and select a three-dimensional volume to physically extract.

For example, isolate the corner of an old jazz club with its piano and tables, or one section of a historic library.

OddHobb generates a clean architectural cutaway, supports it structurally and adds a display base.

Why it's compelling: Customers select a meaningful part of a place without learning modelling tools.

9. Dream Fragments — Stonedoorway

Someone describes a dream or creates an imaginal world. Atlas provides a spatial interpretation, and OddHobb turns a selected scene into a miniature sculpture.

The digital world remains explorable, while the physical object becomes a memorable representation of the experience.

This is an art and journaling product, not a claim to reconstruct someone's actual dream.

10. Impossible Architecture

Generate elaborate imaginary libraries, towers, labyrinths and strange buildings that would take substantial manual modelling to conceive and detail.

Transform them into sculptures, bookends, miniature lamps or decorative collectibles.

Particularly relevant to Ochema's historical architecture and Stonedoorway's imaginal environments.

## 3. The combination with lighting is especially powerful

Atlas-derived scenes could become depth-aware illuminated objects.

A normal personalised photo lamp uses a photograph converted into a lithophane, which is an established technology. JLC even publishes a guide to making them.

But with spatial reconstruction, you could go further: design a layered translucent cityscape with lighting behind different architectural elements, or a miniature remembered room where the windows glow.

The distinction is that you have a spatial model to help decide which surfaces should be separated and illuminated.

I'd test three variants of the same scene: ordinary framed relief, layered backlit relief, and fully three-dimensional cutaway.

That would reveal whether Atlas adds enough quality and emotional value to justify the extra processing.

## 4. The technical pipeline we actually need

The important discovery from JLC's documentation is that full-colour printing accepts textured OBJ files with MTL and PNG textures, as well as supported colour-bearing 3MF or PLY workflows. Uploading a basic STL alone won't preserve a scene's photographic colour.

I'd build the following pipeline:

Photo · Video · Text · Atlas World

Personal memory, real environment or imaginary scene

Atlas / Marble

Spatial reconstruction · Splat · Mesh

OddHobb Physicalisation Compiler

Crop · Scale · Repair mesh · Simplify · Add structural supports · Split into parts

Full-colour sculpture

OBJ + MTL + textures

Mechanical object

Validated STEP/STL/3MF

DIY project kit

Parts + BOM + instructions

Interactive display

Housing + lights + digital scene

JLC + Shenzhen consolidation

Prototype · Manufacture · Inspect · Gift package · Deliver

The difficult middle stage is the one worth owning.

Mesh cleanup alone may not be enough. Some reconstructed scenes have paper-thin geometry, missing backs, inaccessible interiors or texture details that disappear at miniature scale.

So the compiler should select one of several physicalisation strategies:

| Scene type                   | Best physical representation                                             |
| ---------------------------- | ------------------------------------------------------------------------ |
| Room with lots of furniture  | Cutaway miniature or modular kit                                         |
| Street or landscape          | Relief, architectural slice or diorama                                   |
| Dense fantasy architecture   | Solid sculpture                                                          |
| Portrait or memorable moment | Depth relief or volumetric artwork                                       |
| Imaginary interior           | Digital world plus simplified physical shell                             |
| Complex functional mechanism | Rebuild in parametric CAD, rather than directly print reconstructed mesh |

## 5. My highest-priority prototypes

Prototype A — Memory Room

Highest gift potential

A photo-based miniature room, 8–12 cm across, printed in colour, with a base and QR-linked explorable world.

Prototype B — Spatial Photograph

Simplest new manufacturing format

A meaningful photograph converted into a depth relief and mounted as a small sculpture.

Prototype C — Living Fairy Cottage

Best connection to Pogtown

An Atlas-inspired custom cottage exterior, converted into a hollow printable shell with translucent windows, standard LED placement and an optional digital inhabitant.

The Memory Room is where I see the clearest differentiation. CAD tools can build a miniature bedroom, but the customer would normally need to model or commission it manually. With Atlas, the consumer only has to provide the memory.

The Spatial Photograph is the simplest way to validate image-to-physical manufacturing without solving complex assembly.

And the Living Cottage is the long-term platform play because the physical object can be updated with lights, voices, characters and AR over time.

The broader opportunity is a new OddHobb product type:

World Objects — physical keepsakes manufactured from places, memories and imaginary environments.

It's distinct from standard personalised figurines, compatible with the same Shenzhen supply chain, and naturally feeds into your longer-term Pogtown vision of persistent digital places that have physical counterparts.
