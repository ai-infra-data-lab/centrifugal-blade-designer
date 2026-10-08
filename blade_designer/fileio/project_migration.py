"""Pure migrations: source dictionaries and files are never modified."""
from copy import deepcopy
from dataclasses import asdict
from ..models.parameters import BladeParameters


def migrate_v01_to_v02(data):
    source=deepcopy(data)
    try:
        g=source['geometry'];g.pop('n_points')
        a,t=source['angle'],source['thickness']
        if len(a['xi'])!=len(a['alpha_deg']):raise ValueError('v0.1 angle arrays have different lengths.')
        default=asdict(BladeParameters())
        return {'schema_version':'0.2','geometry':g,
            'blade_angle':{'points':[{'m_norm':m,'value':v} for m,v in zip(a['xi'],a['alpha_deg'])]},
            'thickness':{'points':[{'m_norm':0.,'value':t['t_le']},{'m_norm':t['xi_tmax'],'value':t['t_max']},{'m_norm':1.,'value':t['t_te']}]},
            **{k:default[k] for k in ('edges','output_points','export','surface_mapping')}}
    except (KeyError,TypeError) as exc:raise ValueError(f'Malformed v0.1 project: {exc}') from exc


def migrate_v02_to_v03(data):
    result=deepcopy(data)
    defaults=asdict(BladeParameters())
    for key in ('hub','shroud','turbogrid','blade_le_fraction','blade_te_fraction','flow_path','resolution'):
        result[key]=deepcopy(defaults[key])
    try:
        result['sections']=[{'span':span,'blade_angle':deepcopy(result['blade_angle']),
            'thickness':deepcopy(result['thickness']),'edge_parameters':deepcopy(result['edges'])} for span in (0.,1.)]
    except KeyError as exc:raise ValueError(f'Malformed v0.2 project: {exc}') from exc
    result['schema_version']='0.3'
    return result


def migrate_v03_flow_path(data):
    """Upgrade the earlier 0.3 payload without altering existing walls or profiles.

    Earlier 0.3 LE/TE fractions measured the common wall arc-fraction parameter.
    Convert those positions to the mean line's normalized physical distance.
    Preserve legacy wall correspondence; new projects use normal-cut stations.
    """
    result=deepcopy(data)
    defaults=asdict(BladeParameters())
    result.setdefault('resolution',deepcopy(defaults['resolution']))
    try:
        distributions=[result['blade_angle'],result['thickness']]
        distributions += [s[k] for s in result['sections'] for k in ('blade_angle','thickness')]
        for distribution in distributions:
            for point in distribution['points']:
                if 'm_norm' in point:
                    if 'm_blade_norm' in point:raise ValueError('Ambiguous normalized blade coordinate.')
                    point['m_blade_norm']=point.pop('m_norm')
        if 'flow_path' not in result:
            import numpy as np
            from ..models.meridional import MeridionalCurveParameters,LineSegmentParameters,ArcSegmentParameters
            from ..geometry.meridional_segments import generate_meridional
            from ..geometry.flow_path import mean_meridional_line
            def wall(values):
                definition=deepcopy(values)
                definition['segments']=[LineSegmentParameters(**s) if set(s)=={'length'} else ArcSegmentParameters(**s) for s in definition['segments']]
                return generate_meridional(MeridionalCurveParameters(**definition))
            old_le,old_te=result['blade_le_fraction'],result['blade_te_fraction']
            if not np.isfinite([old_le,old_te]).all() or not 0<=old_le<old_te<1:
                raise ValueError('Legacy blade stations require 0 <= LE < TE < OUTLET for diffuser stations.')
            parameter,_,_,m_flow_norm=mean_meridional_line(wall(result['hub']),wall(result['shroud']))
            le,te=map(float,np.interp([old_le,old_te],parameter,m_flow_norm))
            remaining=1-te
            positions=[0.,le,te,te+remaining/3,te+2*remaining/3,1.]
            result['flow_path']={'stations':[{'kind':s['kind'],'m_flow_norm':position} for s,position in zip(defaults['flow_path']['stations'],positions)],
                                 'align_blade_stations_to_crossflow':False}
            result['blade_le_fraction']=le;result['blade_te_fraction']=te
        else:
            result['flow_path'].setdefault('align_blade_stations_to_crossflow',True)
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError(f'Malformed flow-path migration input: {exc}') from exc
    return result
