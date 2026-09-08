import {clientLayer} from "/plugins/leaflet/datatiles-leaflet.js";
import {DataTilesClient} from "/plugins/common/datatiles-client.js";

const styles={
  wrf5_u10m:{title:"10 m eastward wind",unit:"m s⁻¹",palette:[[-15,"#313695"],[0,"#ffffbf"],[15,"#a50026"]]},
  wrf5_v10m:{title:"10 m northward wind",unit:"m s⁻¹",palette:[[-15,"#313695"],[0,"#ffffbf"],[15,"#a50026"]]},
  wrf5_t2c:{title:"2 m air temperature",unit:"°C",palette:[[-15,"#313695"],[0,"#74add1"],[15,"#ffffbf"],[30,"#f46d43"],[45,"#a50026"]]},
  wrf5_slp:{title:"Sea-level pressure",unit:"hPa",palette:[[970,"#313695"],[1000,"#ffffbf"],[1030,"#a50026"]]},
  wrf5_rh2:{title:"2 m relative humidity",unit:"%",palette:[[0,"#fff7bc"],[50,"#7fcdbb"],[100,"#2c7fb8"]]},
  wrf5_delta_rain:{title:"Accumulated rain increment",unit:"source unit",palette:[[0,"#f7fbff"],[2,"#9ecae1"],[10,"#3182bd"],[30,"#08306b"]]},
  wrf5_cldfra_total:{title:"Total cloud fraction",unit:"declared %; fraction-like values",palette:[[0,"#173f67"],[.5,"#91b7d4"],[1,"#ffffff"]]}
};
const config=await fetch("/weather/config.json").then(r=>{if(!r.ok)throw new Error(`configuration HTTP ${r.status}`);return r.json();});
const map=L.map("map",{minZoom:config.minzoom,maxZoom:config.maxzoom});
map.fitBounds([[config.bounds[1],config.bounds[0]],[config.bounds[3],config.bounds[2]]]);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,opacity:.42,attribution:"© OpenStreetMap contributors"}).addTo(map);
const selector=document.querySelector("#variable"),api=new DataTilesClient("");
for(const variable of config.variables.filter(v=>styles[v]))selector.add(new Option(styles[variable].title,variable));
let layer;
function dimensions(coords,variable=selector.value){const domain=config.domainByZoom[String(coords.z)];return {variable,product:"wrf5",domain,valid_time:config.validTimes[0]};}
function setLayer(){
  if(layer)map.removeLayer(layer);const variable=selector.value,style=styles[variable];
  layer=clientLayer(L,"",config.dataset,{palette:style.palette},{dimensions:coords=>dimensions(coords),leaflet:{opacity:.82,attribution:"Meteo@UniParthenope / DataTiles"}}).addTo(map);
  document.querySelector("#title").textContent=style.title;document.querySelector("#time").textContent=config.validTimes[0];
  const gradient=style.palette.map(stop=>`${stop[1]} ${100*(stop[0]-style.palette[0][0])/(style.palette.at(-1)[0]-style.palette[0][0])}%`).join(",");
  document.querySelector("#legend").innerHTML=`<div class="legend-bar" style="background:linear-gradient(90deg,${gradient})"></div><div class="legend-labels"><span>${style.palette[0][0]}</span><span>${style.unit}</span><span>${style.palette.at(-1)[0]}</span></div>`;
}
selector.addEventListener("change",setLayer);setLayer();
function tilePoint(latlng,z){const scale=2**z,gx=(latlng.lng+180)/360*scale,gy=(1-Math.asinh(Math.tan(latlng.lat*Math.PI/180))/Math.PI)/2*scale;return{x:Math.floor(gx),y:Math.floor(gy),px:Math.floor((gx%1)*256),py:Math.floor((gy%1)*256)}}
map.on("click",async event=>{const z=map.getZoom(),p=tilePoint(event.latlng,z),domain=config.domainByZoom[String(z)],status=document.querySelector("#status");try{status.textContent="Decoding exact DNT1 tile…";const decoded=await api.fetchDNT1(config.dataset,z,p.x,p.y,dimensions({z}));const raw=Number(decoded.values[p.py*decoded.header.shape.at(-1)+p.px]),value=raw*(decoded.header.scale??1)+(decoded.header.offset??0);document.querySelector("#value").textContent=`${styles[selector.value].title}: ${value.toPrecision(6)} ${decoded.header.unit||styles[selector.value].unit}`;status.textContent=`XYZ ${z}/${p.x}/${p.y}, pixel ${p.px}/${p.py}; stored numeric value.`;}catch(error){status.textContent=error.message;}});
map.on("zoomend moveend",()=>{const z=map.getZoom();document.querySelector("#zoom").textContent=z;document.querySelector("#domain").textContent=config.domainByZoom[String(z)]||"outside generated range";});map.fire("zoomend");
