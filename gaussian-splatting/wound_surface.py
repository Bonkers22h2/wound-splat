"""Experimental RGB opening and camera-oriented local reference-plane measurement.

Inputs are prediction geometry/colors and an outward direction in the same
coordinate frame. No scanner annotation, target dimension or fitted correction
is used. This is a planar surface estimator, not a clinical validation claim.
"""
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree


def camera_outward(points, camera_positions):
    """Direction toward capture cameras; reject captures on both surface sides."""
    positions=np.asarray(camera_positions,dtype=float)
    if positions.ndim!=2 or positions.shape[1]!=3 or not len(positions) or not np.isfinite(positions).all():
        raise ValueError('Expected finite camera positions in cloud coordinates')
    vectors=positions-np.median(points,axis=0)
    lengths=np.linalg.norm(vectors,axis=1)
    if (lengths<=1e-12).any():
        raise ValueError('Camera coincides with the surface center')
    vectors/=lengths[:,None]
    hint=np.mean(vectors,axis=0)
    if np.linalg.norm(hint)<.5:
        raise ValueError('Ambiguous outward camera direction')
    hint/=np.linalg.norm(hint)
    if np.mean(vectors@hint>.2)<.8:
        raise ValueError('Capture cameras do not agree on outward direction')
    return hint


def _raster(points, red, normal, cell):
    from wound_measure import _plane_basis
    u,v=_plane_basis(normal)
    uv=np.column_stack([points@u,points@v])
    origin=uv.min(axis=0)
    cell=max(cell,float(np.ptp(uv,axis=0).max())/256)
    ij=np.floor((uv-origin)/cell).astype(int)
    shape=ij.max(axis=0)+1
    flat=np.ravel_multi_index(ij.T,shape)
    counts=np.bincount(flat,minlength=int(np.prod(shape)))
    votes=np.bincount(flat,weights=red,minlength=len(counts))
    # Retain the existing auto mode's supported red-point footprint. Majority
    # voting was rejected: layered Gaussian centers fragmented PIS3's opening.
    foreground=(votes>0).reshape(shape)
    labels,n=ndimage.label(foreground,structure=np.ones((3,3)))
    if n==0:
        raise ValueError('No supported RGB wound opening')
    component=labels==np.argmax(np.bincount(labels.ravel())[1:])+1
    opening=ndimage.binary_fill_holes(component)
    cells=np.argwhere(opening)
    if len(cells)<9 or (np.ptp(cells,axis=0)<2).any():
        raise ValueError('RGB wound opening is too small')
    if opening.sum()>.8*np.count_nonzero(counts) or np.all(np.ptp(cells,axis=0)>=.9*(shape-1)):
        raise ValueError('RGB opening spans the crop; surrounding skin is required')
    observed=opening & (counts.reshape(shape)>0)
    supported=(votes.reshape(shape)>counts.reshape(shape)*.5) & observed
    support_fraction=float(supported.sum()/observed.sum())
    return dict(mask=opening,cell=cell,origin=origin,u_axis=u,v_axis=v,
                boundary_support_fraction=support_fraction,
                uv=uv,ij=ij,flat=flat,foreground=foreground)


def _local_skin_plane(points, raster, normal, hint):
    mask,cell=raster['mask'],raster['cell']
    # A ring tied to opening size, independent of how much distant skin is saved.
    distance=ndimage.distance_transform_edt(~mask)*cell
    ring_width=max(3*cell,.15*np.sqrt(mask.sum()*cell**2))
    ring=(distance>0)&(distance<=ring_width)&~raster['foreground']
    ij=raster['ij']
    ids=np.flatnonzero(ring[ij[:,0],ij[:,1]])
    flat=raster['flat'][ids]
    order=np.argsort(flat)
    _,starts=np.unique(flat[order],return_index=True)
    # Equal weight per cell prevents dense patches dominating the skin fit.
    samples=np.array([np.median(points[ids[order[a:b]]],axis=0)
                      for a,b in zip(starts,np.append(starts[1:],len(ids)))])
    if len(samples)<20:
        raise ValueError('Insufficient surrounding skin for a local plane')
    center_uv=np.mean(np.argwhere(mask)+.5,axis=0)*cell+raster['origin']
    sample_uv=np.column_stack([samples@raster['u_axis'],samples@raster['v_axis']])-center_uv
    quadrants=(sample_uv[:,0]>0).astype(int)+2*(sample_uv[:,1]>0)
    if np.count_nonzero(np.bincount(quadrants,minlength=4)>=3)<3:
        raise ValueError('Skin samples do not surround the opening')
    keep=np.ones(len(samples),bool)
    for _ in range(6):
        center=samples[keep].mean(axis=0)
        _,s,vt=np.linalg.svd(samples[keep]-center,full_matrices=False)
        if s[1]<cell:
            raise ValueError('Skin samples cannot define a plane')
        normal=vt[-1]
        if normal@hint<0: normal=-normal
        offset=-float(center@normal)
        residual=samples@normal+offset
        sigma=float(1.4826*np.median(abs(residual[keep]-np.median(residual[keep]))))
        updated=abs(residual)<=max(3*sigma,cell*.01)
        if updated.sum()<20 or np.array_equal(updated,keep): break
        keep=updated
    if normal@hint<.2:
        raise ValueError('Outward direction is nearly tangent to the skin plane')
    return normal,offset,sigma,len(samples)


def measure_surface(points, colors, outward_normal, scale=1.):
    """Return unrounded metrics, coverage and a physical opening footprint.

    Volume/depth are withheld below 98% local surface support. A local median
    of signed depths is clipped at zero only after sampling, so selecting only
    the negative noise tail cannot turn a flat/raised bed into a deep cavity.
    """
    from wound_measure import _color_opening_mask
    points=np.asarray(points,dtype=float)
    colors=np.asarray(colors,dtype=float)
    hint=np.asarray(outward_normal,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<200 or not np.isfinite(points).all():
        raise ValueError('Expected at least 200 finite XYZ points')
    if colors.shape!=points.shape or not np.isfinite(colors).all():
        raise ValueError('Surface mode requires finite RGB colors')
    if hint.shape!=(3,) or not np.isfinite(hint).all() or np.linalg.norm(hint)<1e-12:
        raise ValueError('A finite nonzero outward direction is required')
    if not np.isfinite(scale) or scale<=0:
        raise ValueError('Scale must be finite and positive')
    hint=hint/np.linalg.norm(hint)
    red=_color_opening_mask(colors)
    nn=cKDTree(points).query(points,k=2)[0][:,1]
    nn=nn[nn>0]
    if not len(nn): raise ValueError('Cloud has no spatial extent')
    cell=3*float(np.median(nn))
    _,_,vt=np.linalg.svd(points-points.mean(axis=0),full_matrices=False)
    normal=vt[-1]
    if normal@hint<0: normal=-normal
    raster=_raster(points,red,normal,cell)
    normal,offset,sigma,nskin=_local_skin_plane(points,raster,normal,hint)
    raster=_raster(points,red,normal,cell)
    normal,offset,sigma,nskin=_local_skin_plane(points,raster,normal,hint)
    raster=_raster(points,red,normal,cell)
    mask,cell=raster['mask'],raster['cell']
    queries=(np.argwhere(mask)+.5)*cell+raster['origin']
    ids=raster['ij']
    bed=mask[ids[:,0],ids[:,1]]
    distance,neighbors=cKDTree(raster['uv'][bed]).query(queries,k=min(8,int(bed.sum())))
    distance=distance.reshape(len(queries),-1)
    neighbors=neighbors.reshape(len(queries),-1)
    valid=distance<=cell
    covered=valid.any(axis=1)
    signed_depth=-(points[bed]@normal+offset)
    depths=np.maximum(np.nanmedian(np.where(valid[covered],signed_depth[neighbors[covered]],np.nan),axis=1),0.)
    coverage=float(covered.mean())
    _,_,axes=np.linalg.svd(queries-queries.mean(axis=0),full_matrices=False)
    extent=np.ptp(queries@axes.T,axis=0)+cell*np.abs(axes).sum(axis=1)
    metrics=dict(surface_area_cm2=float(mask.sum()*cell**2*scale**2),
                 volume_cm3=float(depths.sum()*cell**2*scale**3) if coverage>=.98 else None,
                 max_depth_mm=float(depths.max()*scale*10) if coverage>=.98 else None,
                 width_cm=float(min(extent)*scale),height_cm=float(max(extent)*scale))
    footprint={key:raster[key] for key in ('mask','cell','origin','u_axis','v_axis')}
    footprint.update(normal=normal,plane_offset=offset,scale_cm_per_unit=scale,boundary_source='surface_color')
    support=raster['boundary_support_fraction']
    # This is an explicit rejection heuristic, not a calibrated probability.
    # Isolated red points among mostly skin must not silently inflate an opening.
    candidate_metrics=metrics.copy()
    status='experimental' if coverage>=.98 else 'insufficient_coverage'
    if support<.75:
        metrics={key:None for key in metrics}
        status='boundary_review_required'
    return dict(metrics=metrics,diagnostic_candidate_metrics=candidate_metrics,
                boundary_support_fraction=support,coverage=coverage,status=status,
                boundary_source='surface_color',skin_noise_sigma_mm=sigma*scale*10,
                skin_cells=nskin,footprint=footprint)
