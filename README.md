# About

Test transformation math to create an isometric grid.

# Math

## Vector transformation

A 2x2 matrix transforms 2-element column vectors like this:

```
┌     ┐┌    ┐  ┌           ┐
│ a b ││ V1 │ =│ aV1 + bV2 │
│ c d ││ V2 │  │ cV1 + dV2 │
└     ┘└    ┘  └           ┘
```

Context for reading the above in a way that relates to video game maths:

- `V` is a **vector** = (V1,V2)
- `V` is in **coordinate system g** ('g' stands for game art)
- `T` is a 2x2 **transformation matrix**
- `T` transforms the *game art* components of `V` to *OS window pixel* components
  - `T` transforms `V` from coordinate system 'g' to coordinate system 'p' ('p' for pixels)

For example, say a **vector** has components (2,3) in game art coordinate
system `g1,g2`. But the OS doesn't know anything about game art coordinates.
The OS provides the mouse **position** in OS window pixel coordinate system
`p1,p2`.

I want to answer the following question:

**Where is the mouse in the game art coordinate system?**

*I am already confusing points and vectors here, but it's hard to come up with a
simpler example that is relatable. Technically I should only be talking about
vectors. So think of the mouse position as a vector with head at the point of
interest and tail at the topleft of the OS window.*

Let the vector expressed in game art coordinates be `Vg` and the vector in
pixel coordinates be `Vp`. Multiplying `T` by `Vg` yields `Vp`: the same vector
but with its components expressed in the OS window pixel coordinates. Now I can
compare the game art vector with the mouse position because both are in pixel
coordinates.

## Inverse vector transformation

Say I have the opposite problem: I have the mouse in `p1,p2` but I want the
mouse in `g1,g2` to compare the mouse position with objects in the game art.

The inverse of `T` transforms components in `p1,p2` to components in `g1,g2`.
This time `V1,V2` are the components in the **pixel coordinate system** and multiplying
`invT` by `V` transforms the components to the **game art coordinate system**:

```
┌           ┐┌    ┐  ┌                     ┐
│  d/Δ -b/Δ ││ V1 │ =│ ( d/Δ)V1 + (-b/Δ)V2 │
│ -c/Δ  a/Δ ││ V2 │  │ (-c/Δ)V1 + ( a/Δ)V2 │
└           ┘└    ┘  └                     ┘
```

- `Δ` is `ad-bc`

## Point transformation

The 2x2 transformation matrix cannot perform translation. It only performs
scaling, rotation, reflection, or shear. *If that lists sounds overwhelming,
don't worry -- some of transformations are expressible as combinations of the
others. I think the choice of which ones are the "fundamental" operations
just depends on how we set up the matrix arithemtic.*

But back to my example, the mouse position is really a point, not a vector. If
the view in the game art pans, my game art origin point is moving and my 2x2
transformation matrix stops working: my mouse coordinate in game art needs an
offset vector added to it to account for the game art having panned. In other
words, I need to include translation in my transformation matrix.

To include translation, the 2x2 matrix is augmented by an offset column vector,
`O`, and by a third row: `[0 0 1]`.

```
┌       ┐┌    ┐  ┌                ┐
│ a b e ││ V1 │ =│ aV1 + bV2 + e  │
│ c d f ││ V2 │  │ cV1 + dV2 + f  │
│ 0 0 1 ││  1 │  │   0 +   0 + 1  │
└       ┘└    ┘  └                ┘
```

- `V` is a **vector** = (V1,V2)
- `V` is in **coordinate system g** ('g' stands for game art)
- `T` is a 3x3 **transformation matrix** made from a 2x2 **vector transformation matrix** augmented by an offset vector `O`
- `T` transforms the *game art* components of `V` to *OS window pixel* components
  - `T` transforms `V` from coordinate system 'g' to coordinate system 'p' ('p' for pixels)
- `O` is the offset **vector** = (e,f)
  - `O` components are in pixel coordinates
    - Why is `O` in pixel coordinates? Think about the units: we add `O` to `V`
      after the components of `V` are transformed to pixel coordinates. For the
      addition to make sense, both coordinates must be in the same coordinate
      system (in this case, in units of pixels, not units of game art).
  - `O` is a vector with its tail at the origin of `p1,p2` and its head at the
    origin of `g1,g2`
    - Why is `O` directed from the 'p' origin to the 'g' origin? Think about
      the case where `V` is the zero-vector (0,0). Remember `V` is in 'g'
      initially and we are transforming it to 'p'. After the transformation, if
      we do not translate, we have (0,0) in 'p' which is at the topleft of the
      screen. We have to add offset vector `O` to get to the grid origin
      (wherever that is). By the definition of vector addition, that offset
      vector must have its tail at the 'p' origin and its head at the 'g'
      origin.

## Inverse point transformation

There is a general formula for finding the inverse of a 3x3. But in this
special case where the 3x3 is actually a 2x2 transformation matrix augmented
to include translation, there is a simpler formula:

```
┌                     ┐┌    ┐  ┌                                 ┐
│  d/Δ -b/Δ (bf-de)/Δ ││ V1 │ =│ ( d/Δ)V1 + (-b/Δ)V2 + (bf-de)/Δ │
│ -c/Δ  a/Δ (ce-af)/Δ ││ V2 │  │ (-c/Δ)V1 + ( a/Δ)V2 + (ce-af)/Δ │
│    0    0         1 ││  1 │  │        0 +        0 +         1 │
└                     ┘└    ┘  └                                 ┘
```

- `Δ` is `ad-bc`

To derive this formula, I started with the simple case where my two coordinate
systems are simple scalar multiples of each other. In other words, my game art
is a top-down view, like a sheet of graph paper placed directly over the OS
window. With `b=0` and `c=0` it was easy to notice that the offset vector
`(e,f)` in `T` became offset vector `blah` in `invT`. TODO: finish writing this
section.
