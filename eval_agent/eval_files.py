EVAL_FILES = {
    "EvalAgent.cs": r"""
        using UnityEngine;
        using UnityEngine.SceneManagement;
        using UnityEngine.AI;
        using Unity.AI.Navigation;
        using System.IO;
        using System.Text;
        using System.Collections;
        using System.Collections.Generic;
        using System;
        using System.Linq;

        public class EvalAgent : MonoBehaviour
        {
            // ================= DTOs =================
            [Serializable] public class Vec3 { public float x,y,z; public Vec3(){} public Vec3(Vector3 v){x=v.x;y=v.y;z=v.z;} }
            [Serializable] public class CameraInfo { public Vec3 position, rotationEuler, forward; public float fov; }
            [Serializable] public class BoundsInfo { public Vec3 min, max, size; }
            [Serializable] public class ExtractReport { public string scene; public int total; public CameraInfo camera; public BoundsInfo interiorBounds; public PortalEntry[] portals; }
            [Serializable] public class PortalEntry {
                public int id;
                public string name;
                public Vec3 position;
                public Vec3 rotation;
                public Vec3 bounds;
                public string[] reason;

                // ---- Move stage fields ----
                public bool approached;
                public bool transitionOccurred;
                public string destinationScene;
                public string notes;
                public Vec3 spawnPos;
                public Vec3 finalPos;
            }

            // ================= State =================
            string _mode = "extract";
            string _outDir = "eval_out";
            float _timeoutSec = 20f;
            string _version = "normal";

            Camera _sourceMainCam;
            Camera _evalCam;

            GameObject _rig;
            CharacterController _cc;

            Vector3 _spawnPos;
            Quaternion _spawnRot;

            List<PortalEntry> portals;
            ExtractReport _report;
            string _originalScene;
            BoundsInfo _interior;

            // --------- Capture state ----------
            bool _recordingActive = false;
            bool _transitionFlag = false;
            float _transitionTime = 0f;

            // -------- Unity version compatibility shim ----------
            static T[] FindAllActive<T>() where T : UnityEngine.Object
            {
            #if UNITY_2023_1_OR_NEWER
                return UnityEngine.Object.FindObjectsByType<T>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            #else
                return UnityEngine.Object.FindObjectsOfType<T>(includeInactive: false);
            #endif
            }

            void Awake()
            {
                DontDestroyOnLoad(gameObject);
            }

            void Start()
            {
                Debug.Log($"[RUN] Unity Version: {Application.unityVersion}");
                Debug.Log($"[RUN] BatchMode: {Application.isBatchMode}, Platform: {Application.platform}");

                if (!HasArg("-eval"))
                {
                    Debug.Log("[SKIP] -eval flag not present.");
                    return;
                }

                int sceneIndex = GetArgInt("-idx", -1);

                if (sceneIndex >= 0 && SceneManager.GetActiveScene().buildIndex != sceneIndex)
                {
                    Debug.Log($"[BOOT] Loading scene index {sceneIndex}");
                    StartCoroutine(LoadSceneThenRun(sceneIndex));
                    return;
                }

                RunEval();
            }

            void EnsureRuntimeNavMesh()
            {
                // Re-add surface data to NavMesh after loads
                var surfaces = FindAllActive<NavMeshSurface>();
                foreach (var s in surfaces)
                {
                    if (!s.isActiveAndEnabled) s.enabled = true;
                    // Ensure data is present/registered
                    s.RemoveData();
                    s.AddData();
                }
            }

            IEnumerator LoadSceneThenRun(int sceneIndex)
            {
                var op = SceneManager.LoadSceneAsync(sceneIndex);

                while (!op.isDone)
                    yield return null;

                yield return null; // let objects initialize
                EnsureRuntimeNavMesh();

                RunEval();
            }

            void RunEval()
            {
                _mode = (GetArg("-mode") ?? "move").ToLowerInvariant();
                _outDir = GetArg("-out") ?? "eval_out";
                _version = GetArg("-version") ?? "normal";

                try {
                    Directory.CreateDirectory(_outDir);
                    Debug.Log($"[OK] Output directory: {_outDir}");
                } catch (Exception e) {
                    Debug.LogError($"[ERR] Cannot create output directory '{_outDir}': {e.Message}");
                }

                _sourceMainCam = Camera.main;

                if (_sourceMainCam == null)
                {
                    Debug.LogError("[ERR] No MainCamera found in scene.");
                    return;
                }

                _sourceMainCam.gameObject.SetActive(false);

                _originalScene = SceneManager.GetActiveScene().name;
                Debug.Log($"[OK] Original scene: {_originalScene}");

                EnsureRuntimeNavMesh();

                if (_mode == "extract")
                {
                    if (_version == "ab1")
                    {
                        Debug.Log("[RUN] EXTRACT mode (Ablation 1)");
                        RunExtract(true);
                    }
                    else
                    {
                        Debug.Log("[RUN] EXTRACT mode");
                        RunExtract(false);
                    }
                    Debug.Log("[OK] EXTRACT complete. Quitting.");
                    Application.Quit(0);
                    return;
                }

                if (_mode == "test")
                {
                    Debug.Log("[RUN] TEST mode");
                    _report = LoadPortalCandidates();
                    if (_report == null)
                    {
                        Debug.LogError("[Move] Extract file not found.");
                        return;
                    }
                    portals = new List<PortalEntry>(_report.portals);
                    SetupTestCamera();
                    Debug.Log($"[RUN] Begin per-portal evaluation in scene '{_originalScene}'");

                    StartCoroutine(RunTest(portals));
                    return;
                }

                Debug.Log("[RUN] MOVE mode");

                _report = LoadPortalCandidates();

                if (_report == null)
                {
                    Debug.LogError("[Move] Extract file not found.");
                    return;
                }

                portals = new List<PortalEntry>(
                    _report.portals.Where(p => p.transitionOccurred)
                );

                SetupRigAndMainCamera(portals);

                Debug.Log($"[RUN] Begin per-portal evaluation in scene '{_originalScene}'");

                StartCoroutine(RunMove(portals));
            }

            void CloneCameraSettings(Camera src, Camera dst)
            {
                dst.fieldOfView = src.fieldOfView;
                dst.nearClipPlane = 0.02f;
                dst.farClipPlane = 1000f;
                dst.allowHDR = src.allowHDR;
                dst.allowMSAA = src.allowMSAA;
                if (RenderSettings.skybox != null) { dst.clearFlags = CameraClearFlags.Skybox; }
                else { dst.clearFlags = CameraClearFlags.SolidColor; dst.backgroundColor = new Color(0.35f,0.35f,0.35f,1f); }
                dst.cullingMask = ~0;
                dst.depth = 1;
            }

            // ------------------------- EXTRACT -------------------------
            void RunExtract(bool isAb1)
            {
                Physics.queriesHitTriggers = false;
                var scene = SceneManager.GetActiveScene();
                var (portals, _) = FindPortalCandidates(isAb1);
                var camInfo = GetCameraInfo(_sourceMainCam);
                _interior = ComputeInteriorBounds();

                var report = new ExtractReport {
                    scene = scene.name,
                    total = portals.Count,
                    camera = camInfo,
                    interiorBounds = _interior,
                    portals = portals.ToArray()
                };

                var outPath = Path.Combine(_outDir, $"portals_results_{_version}.json");
                File.WriteAllText(outPath, JsonUtility.ToJson(report, true), Encoding.UTF8);
                Debug.Log($"[OK] Extract finished. Wrote {outPath}");
            }

            // ------------------------- Run Test -------------------------
            void SetupTestCamera()
            {
                Debug.Log("[Eval] Setting up rig and evaluation camera...");
                _rig = new GameObject("_EvalRig");

                Vector3 spawn = _sourceMainCam.transform.position;
                _rig.transform.position = spawn;
                _rig.transform.rotation =
                    Quaternion.Euler(0f, _sourceMainCam.transform.eulerAngles.y, 0f);

                _interior = ComputeInteriorBounds();
                float roomHeight = _interior.max.y - _interior.min.y;

                _cc = _rig.AddComponent<CharacterController>();
                _cc.height = 0.1f;
                _cc.radius = 0.1f;
                _cc.center = new Vector3(0, _cc.height * 0.5f, 0);

                var camGO = new GameObject("__EvalCamera");
                _evalCam = camGO.AddComponent<Camera>();
                CloneCameraSettings(_sourceMainCam, _evalCam);
                camGO.transform.SetParent(_rig.transform, worldPositionStays: false);
                camGO.transform.localPosition = Vector3.zero;
                camGO.transform.localRotation = Quaternion.identity;

                // Disable other cameras and any CinemachineBrain to avoid conflicts
                foreach (var c in FindAllActive<Camera>())
                    if (c != _evalCam) c.enabled = false;

                foreach (var beh in FindAllActive<Behaviour>())
                    if (beh != null && beh.GetType().Name == "CinemachineBrain") beh.enabled = false;

                _evalCam.tag = "MainCamera";
                foreach (var c in FindAllActive<Camera>())
                    if (c != _evalCam && c.tag == "MainCamera") c.tag = "Untagged";

                // Persist across scene loads
                DontDestroyOnLoad(_rig);
            }

            IEnumerator RunTest(List<PortalEntry> portals)
            {
                yield return null;

                int index = 0;

                foreach (var p in portals)
                {
                    Debug.Log($"[TEST] Portal {index} id={p.id} name='{p.name}'");

                    PortalEntry entry = _report.portals
                        .FirstOrDefault(x => x.id == p.id);

                    if (entry == null)
                    {
                        Debug.LogWarning($"[TEST] Entry not found for portal {p.id}");
                        continue;
                    }

                    // Reload baseline scene
                    Debug.Log("[TEST] Reloading original scene...");
                    yield return SceneManager.LoadSceneAsync(_originalScene);

                    while (!SceneManager.GetActiveScene().isLoaded)
                        yield return null;

                    yield return null;
                    EnsureRuntimeNavMesh();

                    // Capture scene before trigger
                    string before = SceneManager.GetActiveScene().name;

                    _transitionFlag = false;
                    _transitionTime = 0f;

                    // Respect LevelLoader cooldown
                    yield return new WaitForSeconds(1.1f);

                    Vector3 portalPos = p.position.ToVector3();
                    Quaternion rot = Quaternion.Euler(p.rotation.x, p.rotation.y, p.rotation.z);
                    Vector3 portalForward = rot * Vector3.forward;

                    Collider portalCol = GameObject.Find(p.name)?.GetComponent<BoxCollider>();
                    Vector3 spawnPos;

                    if (portalCol != null)
                    {
                        Bounds b = portalCol.bounds;
                        Debug.Log($"[TEST] Portal {p.name} bound: {b}");

                        // project extents onto the portal forward direction
                        float forwardExtent = Mathf.Abs(Vector3.Dot(b.extents, portalForward.normalized));
                        spawnPos = portalPos + portalForward * (forwardExtent + 0.1f);
                    }
                    else
                    {
                        // fallback
                        spawnPos = portalPos + portalForward * 0.25f;
                    }

                    _rig.transform.position = spawnPos;
                    _rig.transform.rotation = Quaternion.LookRotation((portalPos - spawnPos).normalized);

                    Debug.Log($"[TEST] Spawned at {_rig.transform.position}, {_rig.transform.rotation}, portal at {portalPos}");

                    Physics.SyncTransforms();
                    yield return new WaitForSeconds(0.05f);

                    // Move into portal
                    float moveTime = 0.4f;
                    float timer = 0f;

                    while (timer < moveTime)
                    {
                        Vector3 facing = (portalPos - _rig.transform.position);
                        facing.Normalize();

                        // use transform-based movement
                        _rig.transform.position += facing * 2.5f * Time.deltaTime;

                        timer += Time.deltaTime;
                        yield return null;
                    }
                    Debug.Log($"[TEST] Move to {_rig.transform.position}");

                    // Wait for scene change
                    string destination = null;
                    yield return WaitForSceneChange(before, d => destination = d);

                    if (!string.IsNullOrEmpty(destination))
                    {
                        entry.transitionOccurred = true;
                        entry.destinationScene = destination;

                        Debug.Log($"[TEST] Transition detected -> {destination}");
                    }
                    else
                    {
                        entry.transitionOccurred = false;
                        entry.notes = "no scene change";
                    }

                    var extractPath = Path.Combine(_outDir, $"portals_results_{_version}.json");
                    File.WriteAllText(extractPath, JsonUtility.ToJson(_report, true), Encoding.UTF8);

                    index++;
                }

                Debug.Log("[TEST] Evaluation completed.");
                Application.Quit();
            }

            IEnumerator WaitForSceneChange(string before, Action<string> result)
            {
                float timer = 0f;
                while (timer < _timeoutSec)
                {
                    string current = SceneManager.GetActiveScene().name;
                    if (current != before)
                    {
                        result(current);
                        _transitionFlag = true;
                        _transitionTime = Time.time;
                        yield break;
                    }
                    timer += Time.deltaTime;
                    yield return null;
                }
                result(null);
            }

            // ------------------------- Load Candidates -------------------------
            ExtractReport LoadPortalCandidates()
            {
                string path = Path.Combine(_outDir, $"portals_results_{_version}.json");
                if (!File.Exists(path))
                {
                    Debug.LogWarning($"[WARN] portals_results_{_version}.json not found at {path}. Will fall back to trigger-only scan.");
                    return null;
                }
                string json = File.ReadAllText(path, Encoding.UTF8);
                var report = JsonUtility.FromJson<ExtractReport>(json);
                Debug.Log($"[OK] Loaded {report.portals.Length} portal candidates from {path}");
                return report;
            }

            // ================= Setup rig & camera =================
            void SetupRigAndMainCamera(List<PortalEntry> portals)
            {
                Debug.Log("[Eval] Setting up rig and evaluation camera...");
                EnsureRuntimeNavMesh();
                _rig = new GameObject("_EvalRig");

                Vector3 spawn = ProjectToNavMesh(_sourceMainCam.transform.position);
                
                if (spawn == Vector3.positiveInfinity)
                    {
                        // Try nearest vertex from triangulation
                        var tri = NavMesh.CalculateTriangulation();
                        if (tri.vertices != null && tri.vertices.Length > 0)
                        {
                            int best = 0; 
                            float bestD = ( _sourceMainCam.transform.position - tri.vertices[0]).sqrMagnitude;
                            for (int i = 1; i < tri.vertices.Length; i++)
                            {
                                float d = ( _sourceMainCam.transform.position - tri.vertices[i]).sqrMagnitude;
                                if (d < bestD) { bestD = d; best = i; }
                            }
                            spawn = tri.vertices[best];
                        }
                    }

                if (spawn == Vector3.positiveInfinity)
                    {
                        Debug.LogError("[FATAL] No valid floor NavMesh → skipping run.");

                        Application.Quit(); 
                        return;
                    }
                    
                Debug.Log($"[Spawn] Spawned at {spawn}");
                _spawnPos = spawn;
                _spawnRot = Quaternion.Euler(0f, _sourceMainCam.transform.eulerAngles.y, 0f);
                _rig.transform.position = _spawnPos;
                _rig.transform.rotation = _spawnRot;

                _interior = ComputeInteriorBounds();
                float roomHeight = _interior.max.y - _interior.min.y;

                var camGO = new GameObject("__EvalCamera");
                _evalCam = camGO.AddComponent<Camera>();
                CloneCameraSettings(_sourceMainCam, _evalCam);
                camGO.transform.SetParent(_rig.transform, worldPositionStays: false);
                camGO.transform.localPosition = Vector3.zero;
                camGO.transform.localRotation = Quaternion.identity;

                // Disable other cameras and any CinemachineBrain to avoid conflicts
                foreach (var c in FindAllActive<Camera>())
                    if (c != _evalCam) c.enabled = false;

                foreach (var beh in FindAllActive<Behaviour>())
                    if (beh != null && beh.GetType().Name == "CinemachineBrain") beh.enabled = false;

                _evalCam.tag = "MainCamera";
                foreach (var c in FindAllActive<Camera>())
                    if (c != _evalCam && c.tag == "MainCamera") c.tag = "Untagged";

                // Persist across scene loads
                DontDestroyOnLoad(_rig);
            }

            void SnapToNavMesh()
            {
                NavMeshHit hit;
                if (NavMesh.SamplePosition(_rig.transform.position, out hit, 2f, NavMesh.AllAreas))
                    _rig.transform.position = hit.position;
            }

            // ================= Safe Spawn Positioning =================
            
            Vector3 ProjectToNavMesh(Vector3 preferred)
            {
                NavMeshHit hit;

                // 1) Try a generous direct sample
                if (NavMesh.SamplePosition(preferred, out hit, 3f, NavMesh.AllAreas))
                    return hit.position;

                // 2) Expanding ring in XZ around the seed (covers “nearest anywhere”, not just under)
                float[] radii = { 2f, 4f, 8f };
                for (int rIndex = 0; rIndex < radii.Length; rIndex++)
                {
                    float r = radii[rIndex];
                    const int spokes = 10;
                    for (int i = 0; i < spokes; i++)
                    {
                        float ang = (Mathf.PI * 2f) * (i / (float)spokes);
                        Vector3 probe = new Vector3(
                            preferred.x + Mathf.Cos(ang) * r,
                            preferred.y,
                            preferred.z + Mathf.Sin(ang) * r
                        );
                        if (NavMesh.SamplePosition(probe, out hit, 6f, NavMesh.AllAreas))
                            return hit.position;
                    }
                }

                // 3) As a last resort, snap to the nearest triangle vertex of whatever NavMesh is loaded
                var tri = NavMesh.CalculateTriangulation();
                if (tri.vertices != null && tri.vertices.Length > 0)
                {
                    int best = 0;
                    float bestD = (preferred - tri.vertices[0]).sqrMagnitude;
                    for (int i = 1; i < tri.vertices.Length; i++)
                    {
                        float d = (preferred - tri.vertices[i]).sqrMagnitude;
                        if (d < bestD) { bestD = d; best = i; }
                    }
                    return tri.vertices[best];
                }

                // 4) No navmesh at all (no triangulation) -> report failure
                Debug.LogWarning("[Spawn] Could not find floor NavMesh.");
                return Vector3.positiveInfinity;
            }

            // ================= Move Loop =================
            IEnumerator RunMove(List<PortalEntry> portals)
            {
                yield return null; // wait 1 frame
                
                if (_rig.transform.position == Vector3.positiveInfinity)
                    _rig.transform.position = ProjectToNavMesh(_sourceMainCam.transform.position);

                SnapToNavMesh();
                Debug.Log($"[MOVE] Spawning at {_rig.transform.position}");

                int index = 0;
                foreach (var p in portals)
                {
                    Debug.Log($"[MOVE] Portal {index} id={p.id} name='{p.name}' at {p.position.x:F2},{p.position.y:F2},{p.position.z:F2}");
                    PortalEntry entry = _report.portals
                        .FirstOrDefault(x => x.id == p.id);
                    if (entry == null)
                    {
                        Debug.LogWarning($"[MOVE] Entry not found for portal {p.id}");
                        continue;
                    }

                    if (IsValid(_rig.transform.position))
                        entry.spawnPos = new Vec3(_rig.transform.position);
                    else
                        entry.spawnPos = null;

                    bool reached=false;

                    // Approach the portal
                    Debug.Log("[MOVE] Navigating to portal...");
                    yield return NavMove(p, r => reached = r);
                    Debug.Log($"[MOVE] Ending at {_rig.transform.position}");
                    entry.approached = reached;
                    Debug.Log($"[MOVE] Nav result: approached={reached}");

                    // Ensure recording finishes (either at 20s timeout, or +2s after transition)
                    while (_recordingActive) yield return null;

                    if (IsValid(_rig.transform.position))
                        entry.finalPos = new Vec3(_rig.transform.position);
                    else
                        entry.finalPos = null;

                    var extractPath = Path.Combine(_outDir, $"portals_results_{_version}.json");
                    File.WriteAllText(extractPath, JsonUtility.ToJson(_report, true), Encoding.UTF8);

                    _rig.transform.position = ProjectToNavMesh(_spawnPos);
                    _rig.transform.rotation = _spawnRot;

                    Debug.Log($"[OK] Baseline restored for next portal. New rig pos={_rig.transform.position}");
                    index++;
                }

                Debug.Log("[SUCCESS] Evaluation completed. Exiting player.");
                Application.Quit();
            }

            // ================= NavMesh Movement =================
            IEnumerator NavMove(PortalEntry portal, Action<bool> done)
            {
                done(false);

                // --------- Portal transform data ----------
                Vector3 portalPos = portal.position.ToVector3();
                Quaternion portalRot = Quaternion.Euler(portal.rotation.x, portal.rotation.y, portal.rotation.z);
                Vector3 fwd = portalRot * Vector3.forward;
                Vector3 right = Vector3.Cross(Vector3.up, fwd).normalized;

                // --------- Candidate approach points ----------
                Vector3[] desired =
                {
                    portalPos - fwd * 0.75f,
                    portalPos - fwd * 1.25f,
                    portalPos - fwd * 0.75f + right * 0.5f,
                    portalPos - fwd * 0.75f - right * 0.5f,
                    portalPos - fwd * 1.25f + right * 0.75f,
                    portalPos - fwd * 1.25f - right * 0.75f,
                };

                // Utility lambdas
                float HorizDist(Vector3 a, Vector3 b)
                    => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));

                bool LineOfSight(Vector3 from, Vector3 to)
                {
                    // Small Y offset so don't ray along the floor
                    Vector3 a = from + Vector3.up * 0.6f;
                    Vector3 b = to;
                    Vector3 dir = (b - a);
                    float dist = dir.magnitude;
                    if (dist <= 0.0001f) return true;

                    // Ignore triggers to avoid false blocks from trigger volumes
                    if (Physics.Raycast(a, dir.normalized, out RaycastHit hit, dist, ~0, QueryTriggerInteraction.Ignore))
                    {
                        return hit.distance >= dist - 0.02f;
                    }
                    // No hit at all
                    return true;
                }

                // --------- FAST PATH: find a COMPLETE path to any approach point ----------
                NavMeshHit hit;
                Vector3 goal = Vector3.zero;
                bool foundTarget = false;

                foreach (var d in desired)
                {
                    // Sample a point on the NavMesh near the candidate
                    if (NavMesh.SamplePosition(d, out hit, 3f, NavMesh.AllAreas))
                    {
                        var path = new NavMeshPath();

                        // Try path from current position
                        if (NavMesh.CalculatePath(_rig.transform.position, hit.position, NavMesh.AllAreas, path) &&
                            path.status == NavMeshPathStatus.PathComplete)
                        {
                            goal = hit.position;
                            foundTarget = true;
                            // Walk the corners
                            float speed = 3.5f;
                            foreach (var corner in path.corners)
                            {
                                while (Vector3.Distance(_rig.transform.position, corner) > 0.05f)
                                {
                                    Vector3 step = Vector3.MoveTowards(_rig.transform.position, corner, speed * Time.deltaTime);
                                    _rig.transform.position = step;
                                    SnapToNavMesh();
                                    yield return null;
                                }
                            }
                            done(true);
                            yield break;
                        }

                        // If start might be slightly off-mesh, snap & retry
                        SnapToNavMesh();
                        if (NavMesh.CalculatePath(_rig.transform.position, hit.position, NavMesh.AllAreas, path) &&
                            path.status == NavMeshPathStatus.PathComplete)
                        {
                            goal = hit.position;
                            foundTarget = true;
                            float speed = 3.5f;
                            foreach (var corner in path.corners)
                            {
                                while (Vector3.Distance(_rig.transform.position, corner) > 0.05f)
                                {
                                    Vector3 step = Vector3.MoveTowards(_rig.transform.position, corner, speed * Time.deltaTime);
                                    _rig.transform.position = step;
                                    SnapToNavMesh();
                                    yield return null;
                                }
                            }
                            done(true);
                            yield break;
                        }
                    }
                }

                // --------- FALLBACK: walk to nearest floor point near portal, then ray check ----------
                // 1) Find nearest (XZ-close) floor point on NavMesh near portal
                Vector3 floorGoal = _rig.transform.position; // default to current, will overwrite if found
                bool haveFloor = false;

                // First try directly under/near portal center
                if (NavMesh.SamplePosition(portalPos, out hit, 6f, NavMesh.AllAreas))
                {
                    floorGoal = hit.position;
                    haveFloor = true;
                }
                else
                {
                    // Try a small ring search around the portal in XZ
                    const float r = 2.0f;
                    for (int i = 0; i < 12 && !haveFloor; i++)
                    {
                        float ang = (Mathf.PI * 2f) * (i / 12f);
                        Vector3 probe = new Vector3(portalPos.x + Mathf.Cos(ang) * r, portalPos.y, portalPos.z + Mathf.Sin(ang) * r);
                        if (NavMesh.SamplePosition(probe, out hit, 6f, NavMesh.AllAreas))
                        {
                            floorGoal = hit.position;
                            haveFloor = true;
                        }
                    }
                }

                // 2) If found some floor, move toward it even if path is PARTIAL
                if (haveFloor)
                {
                    var pathToFloor = new NavMeshPath();

                    // Try from current position (snap first for good measure)
                    SnapToNavMesh();
                    if (NavMesh.CalculatePath(_rig.transform.position, floorGoal, NavMesh.AllAreas, pathToFloor) &&
                        pathToFloor.corners != null && pathToFloor.corners.Length > 0)
                    {
                        float speed = 3.5f;
                        foreach (var corner in pathToFloor.corners)
                        {
                            while (Vector3.Distance(_rig.transform.position, corner) > 0.05f)
                            {
                                Vector3 step = Vector3.MoveTowards(_rig.transform.position, corner, speed * Time.deltaTime);
                                _rig.transform.position = step;
                                SnapToNavMesh();
                                yield return null;
                            }
                        }
                    }
                }

                // 3) Decide "approached" by LOS from the reached floor spot
                bool approached = false;
                if (!IsValid(_rig.transform.position) || !IsValid(portalPos))
                {
                    Debug.LogError($"[APPROACH] Invalid agent or portal position: agent={_rig.transform.position}, portal={portalPos}");
                    approached = false;
                }
                else
                {
                    approached = HorizDist(_rig.transform.position, portalPos) <= 0.6f;
                    if (!approached)
                    {
                        // Try LOS to each candidate point; also try the portal center itself
                        foreach (var d in desired)
                        {
                            if (IsValid(d) && LineOfSight(_rig.transform.position, d)) { approached = true; break; }
                        }
                        if (!approached)
                        {
                            // If candidates were obstructed (e.g., inside the wall), try LOS to the portal center
                            approached = LineOfSight(_rig.transform.position, portalPos);
                        }
                    }
                }

                done(approached);
            }

            // ------------------------- Candidate discovery -------------------------
            (List<PortalEntry>, HashSet<int>) FindPortalCandidates(bool isAb1)
            {
                var entries = new List<PortalEntry>(); var seen = new HashSet<int>();
                var colliders = FindAllActive<Collider>();

                static bool HasUserScript(GameObject go)
                {
                    // Get all MonoBehaviours except built-in Transform
                    var scripts = go.GetComponents<MonoBehaviour>();
                    foreach (var s in scripts)
                    {
                        if (s == null) continue; // broken / missing script
                        if (!(s is Transform)) return true;
                    }
                    return false;
                }

                int portalCount = 0;
                foreach (var col in colliders)
                {
                if (col == null) continue;
                var go = col.gameObject;
                if (go.GetComponent<Camera>() != null) continue;

                string n = go.name.ToLowerInvariant();
                bool isTrigger = col.isTrigger;
                bool isScriptAttached = HasUserScript(go);

                if (!isAb1){
                    if (!(isTrigger || isScriptAttached)) continue;
                }

                int key = go.GetInstanceID();
                if (seen.Contains(key)) continue;
                seen.Add(key);

                var b = col.bounds;
                entries.Add(new PortalEntry {
                    id = portalCount++,
                    name = go.name,
                    position = new Vec3(b.center),
                    rotation = new Vec3(go.transform.eulerAngles),
                    bounds = new Vec3(b.size),
                    reason = BuildReasons(isTrigger, isScriptAttached).ToArray()
                });
                }
                Debug.Log($"[OK] Candidate discovery -> {entries.Count} entries.");
                return (entries, seen);
            }

            static List<string> BuildReasons(bool trigger, bool script){ 
                var L=new List<string>();
                if (trigger)L.Add("TriggerCollider");
                if (script)  L.Add("ScriptAttached"); return L;
            }

            BoundsInfo ComputeInteriorBounds()
            {
                var colliders = FindAllActive<Collider>();
                bool hasAny = false; Bounds aabb = new Bounds(Vector3.zero, Vector3.zero);
                foreach (var c in colliders)
                {
                if (c==null || c.isTrigger) continue;
                if (!hasAny){ aabb=c.bounds; hasAny=true; } else aabb.Encapsulate(c.bounds);
                }
                if (!hasAny){ Vector3 cp=_sourceMainCam!=null?_sourceMainCam.transform.position:Vector3.zero; aabb=new Bounds(cp,new Vector3(10,3,10)); }
                return new BoundsInfo{ min=new Vec3(aabb.min), max=new Vec3(aabb.max), size=new Vec3(aabb.size) };
            }

            CameraInfo GetCameraInfo(Camera cam)
            {
                var t = cam.transform;
                return new CameraInfo { position=new Vec3(t.position), rotationEuler=new Vec3(t.eulerAngles), forward=new Vec3(t.forward), fov=cam.fieldOfView };
            }

            // ================= CLI =================
            static bool HasArg(string n)
            {
                foreach(var a in Environment.GetCommandLineArgs())
                if(a==n) return true;
                return false;
            }

            static string GetArg(string n)
            {
                var args=Environment.GetCommandLineArgs();
                for(int i=0;i<args.Length-1;i++)
                if(args[i]==n) return args[i+1];
                return null;
            }

            static int GetArgInt(string name, int fallback)
            {
                string s = GetArg(name);
                if (int.TryParse(s, out int v))
                    return v;
                return fallback;
            }

            bool IsValid(Vector3 v)
            {
                return !(float.IsNaN(v.x) || float.IsInfinity(v.x) ||
                        float.IsNaN(v.y) || float.IsInfinity(v.y) ||
                        float.IsNaN(v.z) || float.IsInfinity(v.z));
            }
        }

        // helper extension 
        static class VecExt
        {
            public static Vector3 ToVector3(this EvalAgent.Vec3 v) => new Vector3(v.x,v.y,v.z);
        }
    """,
    "CapturePortals.cs": r"""
        using UnityEngine;
        using System.Collections;
        using System.Collections.Generic;
        using System.IO;
        using System;

        public class CapturePortals : MonoBehaviour
        {
            // ---------------- JSON DTOs ----------------

            [Serializable]
            public class Vec3
            {
                public float x, y, z;
                public Vector3 ToV() => new Vector3(x, y, z);
            }

            [Serializable]
            public class BoundsInfo
            {
                public Vec3 min, max, size;
            }

            [Serializable]
            public class PortalEntry
            {
                public int id;
                public string name;
                public bool transitionOccurred;
            }

            [Serializable]
            public class Report
            {
                public string scene;
                public BoundsInfo interiorBounds;
                public PortalEntry[] portals;
            }

            // ---------------- Config ----------------

            string _jsonPath;
            string _outDir;
            Camera _cam;

            Bounds _roomBounds;

            // ---------------- Entry ----------------
            void Start()
            {
                Debug.Log("[Orbit] Script started.");

                if (!HasArg("-orbitCapture"))
                    return;

                int sceneIndex = GetArgInt("-idx", -1);
                _roomBounds = ComputeInteriorBounds();

                if (sceneIndex >= 0 &&
                    UnityEngine.SceneManagement.SceneManager.GetActiveScene().buildIndex != sceneIndex)
                {
                    Debug.Log($"[Orbit] Loading scene index {sceneIndex}");
                    StartCoroutine(LoadSceneThenRun(sceneIndex));
                    return;
                }

                RunOrbitCapture();
            }

            IEnumerator LoadSceneThenRun(int sceneIndex)
            {
                var op = UnityEngine.SceneManagement.SceneManager.LoadSceneAsync(sceneIndex);

                while (!op.isDone)
                    yield return null;

                yield return null; // let objects initialize

                RunOrbitCapture();
            }

            void RunOrbitCapture()
            {
                _jsonPath = GetArg("-results");
                _outDir = GetArg("-out");

                if (!File.Exists(_jsonPath))
                {
                    Debug.LogError("[Orbit] JSON not found.");
                    Application.Quit(1);
                    return;
                }

                Directory.CreateDirectory(_outDir);

                var json = File.ReadAllText(_jsonPath);
                var report = JsonUtility.FromJson<Report>(json);

                _cam = new GameObject("__OrbitCamera").AddComponent<Camera>();
                _cam.tag = "MainCamera";

                StartCoroutine(CaptureAll(report));
            }

            Bounds ComputeInteriorBounds()
            {
                var colliders = FindObjectsOfType<Collider>();

                bool hasAny = false;
                Bounds aabb = new Bounds(Vector3.zero, Vector3.zero);

                float camY = (_cam != null) ? _cam.transform.position.y : 0f;

                foreach (var c in colliders)
                {
                    if (c == null || c.isTrigger) continue;

                    Bounds b = c.bounds;

                    if (!hasAny)
                    {
                        aabb = b;
                        hasAny = true;
                    }
                    else
                    {
                        aabb.Encapsulate(b);
                    }
                }

                // fallback if nothing found
                if (!hasAny)
                {
                    Vector3 center = (_cam != null)
                        ? _cam.transform.position
                        : Vector3.zero;

                    aabb = new Bounds(center, new Vector3(10f, 3f, 10f));

                    Debug.LogWarning("[Bounds] Fallback bounds used.");
                }

                Debug.Log($"[Bounds] Computed: center={aabb.center}, size={aabb.size}");

                return aabb;
            }

            bool IsStrictlyInside(Bounds b, Vector3 p, float margin = 0.1f)
            {
                return
                    p.x > b.min.x + margin && p.x < b.max.x - margin &&
                    p.y > b.min.y + margin && p.y < b.max.y - margin &&
                    p.z > b.min.z + margin && p.z < b.max.z - margin;
            }

            bool HasVisibleRenderer(Collider col)
            {
                var r = col.GetComponent<Renderer>();
                return r != null && r.enabled;
            }

            bool IsMatch(Collider col, string targetName)
            {
                if (col.name == targetName)
                    return true;

                // parent hierarchy
                Transform t = col.transform;
                while (t != null)
                {
                    if (t.name == targetName)
                        return true;
                    t = t.parent;
                }

                return false;
            }

            bool IsVisible(Collider targetCol, Vector3 camPos, string targetName)
            {
                Vector3 target = targetCol.bounds.center;
                Vector3 dir = target - camPos;
                float dist = dir.magnitude;
                Ray ray = new Ray(camPos, dir.normalized);
                RaycastHit[] hits = Physics.RaycastAll(ray, dist + 0.1f, ~0, QueryTriggerInteraction.Collide);

                System.Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));
                foreach (var hit in hits)
                {
                    Collider col = hit.collider;
                    if (!HasVisibleRenderer(col))
                        continue;
                    if (col.name == "MainCamera" || col.CompareTag("MainCamera"))
                        continue;
                    if (IsMatch(col, targetName))
                        return true;

                    Debug.Log($"[VIS] Blocked by {col.name}");
                    return false;
                }
                return false;
            }

            // ---------------- Main Orbit Logic ----------------

            IEnumerator CaptureAll(Report report)
            {
                foreach (var p in report.portals)
                {
                    if (!p.transitionOccurred)
                        continue;

                    Debug.Log($"[Orbit] Capturing {p.name}");

                    GameObject portalGO = GameObject.Find(p.name);
                    if (!portalGO) continue;

                    Collider portalCol = portalGO.GetComponent<Collider>();
                    if (!portalCol) continue;

                    Bounds pb = portalCol.bounds;
                    Vector3 center = pb.center;

                    string folder = Path.Combine(_outDir, $"{p.id:000}_{Sanitize(p.name)}");

                    if (Directory.Exists(folder))
                        Directory.Delete(folder, true);

                    Directory.CreateDirectory(folder);

                    Vector3 forward = portalGO.transform.forward;
                    Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;

                    // ---- Compute adaptive radius based on FOV ----
                    float width  = pb.size.x;
                    float depth  = pb.size.z;
                    float heightObj = pb.size.y;

                    float fovRad = _cam.fieldOfView * Mathf.Deg2Rad;
                    float maxHorizontalSize = Mathf.Max(width, depth);

                    // Fit object in view
                    float radius_w = (maxHorizontalSize * 0.6f) / Mathf.Tan(fovRad * 0.5f);
                    float radius_h = (heightObj * 0.6f) / Mathf.Tan(fovRad * 0.5f);
                    float radius = Mathf.Max(radius_w, radius_h);

                    // Clamp to prevent extreme distances
                    radius = Mathf.Clamp(radius, 1.5f, 6f);

                    // Slight elevation (30% above center)
                    float camHeightOffset = heightObj * 0.3f;

                    float[] anglesDeg = { 0f, 45f, 90f, 135f, 180f, 225f, 270f, 315f };

                    int index = 0;

                    foreach (float angleDeg in anglesDeg)
                    {
                        float angle = angleDeg * Mathf.Deg2Rad;

                        Vector3 dir =
                            forward * Mathf.Cos(angle) +
                            right * Mathf.Sin(angle);

                        Vector3 camPos = center + dir * radius;
                        camPos.y = center.y + camHeightOffset;

                        if (!IsVisible(portalCol, camPos, p.name))
                        {
                            Debug.Log($"[Orbit] Skipping {angleDeg}° (occluded)");
                            continue;
                        }

                        _cam.transform.position = camPos;

                        // Look slightly above center for balanced framing
                        Vector3 lookTarget = center + Vector3.up * (heightObj * 0.15f);
                        _cam.transform.LookAt(lookTarget);

                        yield return new WaitForEndOfFrame();
                        CaptureFrame(folder, index++);
                    }
                }

                Debug.Log("[Orbit] Done.");
                Application.Quit();
            }

            // ---------------- Capture ----------------

            void CaptureFrame(string folder, int index)
            {
                int width = 1024;
                int height = 768;

                RenderTexture rt = new RenderTexture(width, height, 24);
                Texture2D tex = new Texture2D(width, height, TextureFormat.RGB24, false);

                _cam.targetTexture = rt;
                _cam.Render();

                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();

                File.WriteAllBytes(
                    Path.Combine(folder, $"{index:000}.png"),
                    tex.EncodeToPNG()
                );

                _cam.targetTexture = null;
                RenderTexture.active = null;

                Destroy(rt);
                Destroy(tex);
            }

            // ---------------- CLI ----------------

            static bool HasArg(string name)
            {
                foreach (var a in Environment.GetCommandLineArgs())
                    if (a == name) return true;
                return false;
            }

            static string GetArg(string name)
            {
                var args = Environment.GetCommandLineArgs();
                for (int i = 0; i < args.Length - 1; i++)
                    if (args[i] == name) return args[i + 1];
                return null;
            }

            static int GetArgInt(string name, int fallback = -1)
            {
                string s = GetArg(name);
                if (int.TryParse(s, out int v))
                    return v;
                return fallback;
            }

            string Sanitize(string s)
            {
                foreach (var c in Path.GetInvalidFileNameChars())
                    s = s.Replace(c, '_');
                return s;
            }
        }
    """,
    "EvalBootstrap.cs": r"""
        using UnityEngine;

        public class EvalBootstrap
        {
            [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
            static void Init()
            {
                if (HasArg("-orbitCapture"))
                {
                    var go = new GameObject("__OrbitCapture");
                    Object.DontDestroyOnLoad(go);
                    go.AddComponent<CapturePortals>();
                    return;
                }

                if (HasArg("-eval"))
                {
                    var go = new GameObject("__EvalAgent");
                    Object.DontDestroyOnLoad(go);
                    go.AddComponent<EvalAgent>();
                    return;
                }
            }

            static bool HasArg(string name)
            {
                foreach (var a in System.Environment.GetCommandLineArgs())
                    if (a == name) return true;
                return false;
            }
        }
    """,
    "BuildEval.cs": r"""
        #if UNITY_EDITOR
        using UnityEditor;
        using UnityEngine;
        using UnityEditor.Build.Reporting;
        using System.IO;
        using System;
        using System.Linq;

        public static class BuildEval
        {
            public static void Build()
            {
                Debug.Log("[BuildEval] Building EVAL executable");

                string[] scenes = AssetDatabase.FindAssets("t:Scene")
                    .Select(AssetDatabase.GUIDToAssetPath)
                    .Where(p => p.StartsWith("Assets/Scenes", StringComparison.OrdinalIgnoreCase))
                    .OrderBy(p => p)
                    .ToArray();

                if (scenes.Length == 0)
                {
                    Debug.LogError("[BuildEval] No scenes found under Assets/Scenes");
                    return;
                }

                EditorBuildSettings.scenes = scenes
                    .Select(s => new EditorBuildSettingsScene(s, true))
                    .ToArray();

                BuildTarget buildTarget; string evalPath;

                if (Application.platform == RuntimePlatform.OSXEditor) {
                    buildTarget = BuildTarget.StandaloneOSX;
                    evalPath = "Builds/EvalBuilds/evalworld.app";
                } else if (Application.platform == RuntimePlatform.WindowsEditor) {
                    buildTarget = Environment.Is64BitOperatingSystem ? BuildTarget.StandaloneWindows64 : BuildTarget.StandaloneWindows;
                    evalPath = "Builds/EvalBuilds/evalworld.exe";
                } else if (Application.platform == RuntimePlatform.LinuxEditor) {
                    buildTarget = BuildTarget.StandaloneLinux64;
                    evalPath = "Builds/EvalBuilds/evalworld.x86_64";
                } else {
                    Debug.LogError($"[BuildEval] Unsupported platform {Application.platform}");
                    return;
                }

                if (!Directory.Exists("Builds/EvalBuilds")) Directory.CreateDirectory("Builds/EvalBuilds");

                BuildPlayerOptions evalBuild = new BuildPlayerOptions {
                    scenes = scenes,
                    locationPathName = evalPath,
                    target = buildTarget,
                    options = BuildOptions.None
                };

                BuildSummary summary = BuildPipeline.BuildPlayer(evalBuild).summary;
                Debug.Log(summary.result == BuildResult.Succeeded
                ? $"[BuildEval] Eval build succeeded ({summary.totalSize} bytes)"
                : "[BuildEval] Eval build FAILED");
            }
        }
    #endif
    """,
    "AutoBakeNavMesh.cs": r"""
        #if UNITY_EDITOR
        using UnityEditor;
        using UnityEditor.SceneManagement;
        using UnityEngine;
        using UnityEngine.AI;
        using Unity.AI.Navigation;
        using System.Collections.Generic;
        using System.Linq;

        public static class AutoBakeNavMesh
        {
            private const string SurfaceName = "__NavMeshSurface";
            private const string ScenesRoot  = "Assets/Scenes";
            private const string DataFolder  = "Assets/NavMeshData";

            private const float AGENT_RADIUS = 0.05f;
            private const float AGENT_HEIGHT = 1.2f;

            public static void Bake()
            {
                var sceneGuids = AssetDatabase.FindAssets("t:Scene");
                var scenes = sceneGuids
                    .Select(AssetDatabase.GUIDToAssetPath)
                    .Where(p => p.StartsWith(ScenesRoot))
                    .ToArray();

                if (scenes.Length == 0)
                {
                    Debug.LogWarning($"[AutoBake] No scenes found under {ScenesRoot}");
                    return;
                }

                if (!AssetDatabase.IsValidFolder(DataFolder))
                    AssetDatabase.CreateFolder("Assets", "NavMeshData");

                var activeScenePath = EditorSceneManager.GetActiveScene().path;

                try
                {
                    foreach (var path in scenes)
                    {
                        var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                        Debug.Log($"[AutoBake] Baking {scene.name}");

                        // Destroy any existing __NavMeshSurface to ensure clean state
                        var oldSurfaceGO = GameObject.Find(SurfaceName);
                        if (oldSurfaceGO != null)
                        {
                            Object.DestroyImmediate(oldSurfaceGO);
                            Debug.Log($"[AutoBake] Destroyed old {SurfaceName} GameObject before baking.");
                        }

                        // Ensure a single NavMeshSurface exists on a dedicated GO
                        var surfaceGO = new GameObject(SurfaceName);
                        var surface   = surfaceGO.AddComponent<NavMeshSurface>();

                        // Keep the helper object tidy & out of builds
                        surfaceGO.tag = "Untagged";

                        // Collection/filter settings
                        surface.collectObjects    = CollectObjects.All;
                        surface.layerMask         = ~0;
                        surface.useGeometry       = NavMeshCollectGeometry.RenderMeshes;
                        surface.overrideVoxelSize = true;
                        surface.voxelSize         = AGENT_RADIUS / 8f;

                        // Log number of NavMeshSurfaces in scene
                        var allSurfaces = Object.FindObjectsOfType<NavMeshSurface>();
                        Debug.Log($"[AutoBake] NavMeshSurfaces in scene before bake: {allSurfaces.Length}");

                        // Build with custom agent radius/height
                        if (!BuildSurfaceWithCustomAgent(surface, AGENT_RADIUS, AGENT_HEIGHT))
                        {
                            Debug.LogWarning($"[AutoBake] {scene.name}: Build produced no navMeshData.");
                        }
                        else
                        {
                            // Persist the baked data as an asset and reassign it to the surface
                            var assetPath = $"{DataFolder}/{scene.name}_NavMesh.asset";

                            var existing = AssetDatabase.LoadAssetAtPath<NavMeshData>(assetPath);
                            if (existing != null)
                                AssetDatabase.DeleteAsset(assetPath);

                            var data = surface.navMeshData;

                            if (data == null)
                            {
                                Debug.LogError($"[AutoBake] {scene.name}: navMeshData is null after build.");
                                return;
                            }

                            AssetDatabase.CreateAsset(data, assetPath);
                            AssetDatabase.SaveAssets();

                            surface.RemoveData();
                            surface.navMeshData = AssetDatabase.LoadAssetAtPath<NavMeshData>(assetPath);
                            surface.AddData();
                            EditorUtility.SetDirty(surface);
                        }

                        // Save the scene so the surface + reference are serialized
                        EditorSceneManager.MarkSceneDirty(scene);
                        EditorSceneManager.SaveScene(scene);
                        Debug.Log($"[AutoBake] Done: {scene.name}");
                    }

                    AssetDatabase.SaveAssets();
                    Debug.Log("[AutoBake] ALL DONE");
                }
                finally
                {
                    // Restore previously active scene
                    if (!string.IsNullOrEmpty(activeScenePath))
                        EditorSceneManager.OpenScene(activeScenePath, OpenSceneMode.Single);

                }
            }

            /// Uses NavMeshBuilder.UpdateNavMeshData with custom NavMeshBuildSettings
            private static bool BuildSurfaceWithCustomAgent(NavMeshSurface surface, float agentRadius, float agentHeight)
            {
                // Start from the surface's agent type
                var settings = NavMesh.GetSettingsByID(surface.agentTypeID);

                // Override agent size for this bake
                settings.agentRadius = agentRadius;
                settings.agentHeight = agentHeight;

                // Respect surface overrides
                if (surface.overrideVoxelSize)
                {
                    settings.overrideVoxelSize = true;
                    settings.voxelSize         = surface.voxelSize;
                }
                if (surface.overrideTileSize)
                {
                    settings.overrideTileSize = true;
                    settings.tileSize         = surface.tileSize;
                }

                // Collect sources using the surface
                var sources = new List<NavMeshBuildSource>();
                var markups = new List<NavMeshBuildMarkup>();

                switch (surface.collectObjects)
                {
                    case CollectObjects.All:
                        // Collect across the whole scene
                        NavMeshBuilder.CollectSources(
                            null,
                            surface.layerMask,
                            surface.useGeometry,
                            surface.defaultArea,
                            markups,
                            sources
                        );
                        break;

                    case CollectObjects.Children:
                        NavMeshBuilder.CollectSources(
                            surface.transform,
                            surface.layerMask,
                            surface.useGeometry,
                            surface.defaultArea,
                            markups,
                            sources
                        );
                        break;

                    case CollectObjects.Volume:
                        var worldBounds = new Bounds(
                            surface.transform.TransformPoint(surface.center),
                            Vector3.Scale(surface.size, surface.transform.lossyScale)
                        );

                        NavMeshBuilder.CollectSources(
                            worldBounds,
                            surface.layerMask,
                            surface.useGeometry,
                            surface.defaultArea,
                            markups,
                            sources
                        );
                        break;
                }

                Debug.Log($"[AutoBake] Sources collected: {sources.Count}");

                // Compute bounds
                var bounds = surface.navMeshData != null
                    ? surface.navMeshData.sourceBounds
                    : CalculateWorldBounds(surface, sources);

                Debug.Log($"[AutoBake] Calculated bounds: center={bounds.center}, size={bounds.size}");

                // Ensure a NavMeshData to bake into
                if (surface.navMeshData == null)
                    surface.navMeshData = new NavMeshData(surface.agentTypeID);

                // Update data with custom settings
                var updated = NavMeshBuilder.UpdateNavMeshData(surface.navMeshData, settings, sources, bounds);

                if (updated)
                {
                    Debug.Log($"[AutoBake] Baked with agentRadius={settings.agentRadius}, agentHeight={settings.agentHeight}, voxel={settings.voxelSize} (overrideVoxel={settings.overrideVoxelSize})");
                    surface.RemoveData();
                    surface.AddData();
                }

                return updated;
            }

            private static Bounds CalculateWorldBounds(NavMeshSurface surface, List<NavMeshBuildSource> sources)
            {
                var hasBounds = false;
                var bounds = new Bounds();

                foreach (var src in sources)
                {
                    switch (src.shape)
                    {
                        case NavMeshBuildSourceShape.Mesh:
                        {
                            var m = src.sourceObject as Mesh;
                            if (m == null) break;
                            var world = TransformBounds(src.transform, m.bounds);
                            if (!hasBounds) { bounds = world; hasBounds = true; }
                            else bounds.Encapsulate(world);
                            break;
                        }
                        case NavMeshBuildSourceShape.Terrain:
                        {
                            var t = src.sourceObject as TerrainData;
                            if (t == null) break;
                            var tb = new Bounds(t.size * 0.5f, t.size);
                            var world = TransformBounds(src.transform, tb);
                            if (!hasBounds) { bounds = world; hasBounds = true; }
                            else bounds.Encapsulate(world);
                            break;
                        }
                        default:
                        {
                            var world = TransformBounds(src.transform, new Bounds(Vector3.zero, Vector3.one));
                            if (!hasBounds) { bounds = world; hasBounds = true; }
                            else bounds.Encapsulate(world);
                            break;
                        }
                    }
                }

                if (hasBounds) bounds.Expand(0.1f);
                else bounds = new Bounds(surface.transform.position, Vector3.one * 1000f);

                return bounds;
            }

            private static Bounds TransformBounds(Matrix4x4 m, Bounds b)
            {
                var center = m.MultiplyPoint3x4(b.center);

                var ext = b.extents;
                var ax = m.MultiplyVector(new Vector3(ext.x, 0, 0));
                var ay = m.MultiplyVector(new Vector3(0, ext.y, 0));
                var az = m.MultiplyVector(new Vector3(0, 0, ext.z));
                ext.x = Mathf.Abs(ax.x) + Mathf.Abs(ay.x) + Mathf.Abs(az.x);
                ext.y = Mathf.Abs(ax.y) + Mathf.Abs(ay.y) + Mathf.Abs(az.y);
                ext.z = Mathf.Abs(ax.z) + Mathf.Abs(ay.z) + Mathf.Abs(az.z);

                return new Bounds(center, ext * 2f);
            }
        }
        #endif
    """,
    "AutoInstallNavMesh.cs": r"""
        #if UNITY_EDITOR
        using UnityEditor;
        using UnityEditor.PackageManager;
        using UnityEditor.PackageManager.Requests;
        using UnityEngine;
        using System.Linq;

        [InitializeOnLoad]
        public static class AutoInstallNavMesh
        {
            public static void Install()
            {
                var list = Client.List(true);
                while (!list.IsCompleted) {}

                if (list.Result.Any(p => p.name == "com.unity.ai.navigation"))
                {
                    Debug.Log("[Eval] AI Navigation already installed.");
                    return;
                }

                Debug.Log("[Eval] Installing AI Navigation...");
                var request = Client.Add("com.unity.ai.navigation");
                while (!request.IsCompleted) {}

                if (request.Status == StatusCode.Success)
                    Debug.Log("[Eval] AI Navigation installed successfully.");
                else
                    Debug.LogError("[Eval] Install failed: " + request.Error.message);
            }
        }
        #endif
    """
}