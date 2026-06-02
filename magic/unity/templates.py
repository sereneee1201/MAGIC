# -*- coding: utf-8 -*-

SCENE_BUILDER_TEMPLATE = """#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

public class Logger_{scene_idx}
{{
    public static void Log(string message)
    {{
        Debug.Log($"[Scene {scene_idx}] {{message}}");
    }}
}}

public class SceneBuilder_{scene_idx}
{{
    private static List<GameObject> normalObjects = new List<GameObject>();
    private static List<GameObject> connections = new List<GameObject>();
    private static List<GameObject> floors = new List<GameObject>();
    private static List<GameObject> nonfloors = new List<GameObject>();
    private static List<GameObject> walls = new List<GameObject>();

    public static void BuildScene()
    {{
        Logger_{scene_idx}.Log("BuildScene()");

        var newScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        AddCamera("MainCamera", position: {camera_position}, lookAt: {camera_look_at});
        GameObject renderCamera = AddCamera("RenderCamera");
        new GameObject("Keyboard_{scene_idx}").AddComponent<Keyboard_{scene_idx}>();
        new GameObject("Overlay_{scene_idx}").AddComponent<Overlay_{scene_idx}>();
        new GameObject("BoundingBoxDrawer_{scene_idx}").AddComponent<BoundingBoxDrawer_{scene_idx}>();
        new GameObject("ARDemo_{scene_idx}").AddComponent<ARDemo_{scene_idx}>();{ground}{objects}{point_lights}

        // ----- Toggle controllers -----
        ToggleController_{scene_idx} normalObjectsToggler = new GameObject("NormalObjectsToggler").AddComponent<ToggleController_{scene_idx}>();
        normalObjectsToggler.objectsToToggle = normalObjects.ToArray();
        normalObjectsToggler.key = KeyCode.O;

        ToggleController_{scene_idx} connectionsToggler = new GameObject("ConnectionsToggler").AddComponent<ToggleController_{scene_idx}>();
        connectionsToggler.objectsToToggle = connections.ToArray();
        connectionsToggler.key = KeyCode.C;

        ToggleController_{scene_idx} floorsToggler = new GameObject("FloorsToggler").AddComponent<ToggleController_{scene_idx}>();
        floorsToggler.objectsToToggle = floors.ToArray();
        floorsToggler.key = KeyCode.F;

        ToggleController_{scene_idx} nonfloorsToggler = new GameObject("NonfloorsToggler").AddComponent<ToggleController_{scene_idx}>();
        nonfloorsToggler.objectsToToggle = nonfloors.ToArray();
        nonfloorsToggler.key = KeyCode.I;

        ToggleController_{scene_idx} wallsToggler = new GameObject("WallsToggler").AddComponent<ToggleController_{scene_idx}>();
        wallsToggler.objectsToToggle = walls.ToArray();
        wallsToggler.key = KeyCode.T;
        wallsToggler.Toggle();
        // ==============================

        if (!AssetDatabase.IsValidFolder("Assets/Scenes"))
        {{
            AssetDatabase.CreateFolder("Assets", "Scenes");
        }}
        string scenePath = "Assets/Scenes/MainScene_{scene_idx}.unity";
        EditorSceneManager.SaveScene(newScene, scenePath);
        Logger_{scene_idx}.Log($"Scene built: {{scenePath}}");
    }}

    private static GameObject AddCamera(string name, Vector3 position = default, Vector3 lookAt = default)
    {{
        if (position == lookAt && position == Vector3.zero)
        {{
            position = new Vector3(1f, 1f, 1f);
            lookAt = new Vector3(0.5f, 0.5f, 1f);
        }}

        Logger_{scene_idx}.Log($"AddCamera({{name}}, {{position}}, {{lookAt}})");

        GameObject cameraObject = new GameObject(name);
        Camera camera = cameraObject.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = Color.white;
        cameraObject.transform.position = position;
        cameraObject.transform.LookAt(lookAt);
        if (name.Contains("Main"))
        {{
            cameraObject.AddComponent<CameraController_{scene_idx}>();
            Rigidbody rigidBody = cameraObject.AddComponent<Rigidbody>();
            rigidBody.useGravity = false;
            BoxCollider boxCollider = cameraObject.AddComponent<BoxCollider>();
            boxCollider.isTrigger = true;
            cameraObject.tag = "MainCamera";
            camera.depth = 1;
        }}
        return cameraObject;
    }}

    private static GameObject AddGround(Vector3 scale = default, Vector3 position = default)
    {{
        if (scale == Vector3.zero)
        {{
            scale = new Vector3(100f, 1f, 100f);
        }}

        Logger_{scene_idx}.Log($"AddGround({{scale}}, {{position}})");

        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.position = position;
        ground.transform.localScale = scale;

        return ground;
    }}

    private static void ApplyTextures(GameObject model, string albedoPath, string emissionPath, string normalPath)
    {{
        Texture2D albedoTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(albedoPath);
        Texture2D emissionTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(emissionPath);
        Texture2D normalTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(normalPath);
        foreach (var renderer in model.GetComponentsInChildren<MeshRenderer>())
        {{
            Material material = renderer.material;
            if (albedoTexture != null)
            {{
                material.SetTexture("_MainTex", albedoTexture);
            }}
            if (emissionTexture != null)
            {{
                material.SetTexture("_EmissionMap", emissionTexture);
                material.EnableKeyword("_EMISSION");
            }}
            if (normalTexture != null)
            {{
                material.SetTexture("_BumpMap", normalTexture);
            }}
        }}
    }}

#nullable enable
    private static GameObject? LoadAnyObject(string dirname, string name, Vector3 position = default, Vector3 rotation = default, Vector3 scale = default)
#nullable disable
    {{
        if (scale == Vector3.zero)
        {{
            scale = new Vector3(1f, 1f, 1f);
        }}
        // scale.x *= -1;
        // scale.z *= -1;

        string objDir = $"Assets/Models/{{dirname}}";
        GameObject model = AssetDatabase.LoadAssetAtPath<GameObject>($"{{objDir}}/mesh.obj");
        if (model != null)
        {{
            GameObject instance = UnityEngine.Object.Instantiate(model, position, Quaternion.Euler(rotation));
            instance.transform.localScale = scale;
            instance.name = name;

            // Ensure Renderer, MeshFilter, and MeshCollider components on all child objects
            foreach (Transform child in instance.GetComponentsInChildren<Transform>())
            {{
                MeshRenderer meshRenderer = child.gameObject.GetComponent<MeshRenderer>();
                if (meshRenderer == null)
                {{
                    meshRenderer = child.gameObject.AddComponent<MeshRenderer>();
                }}

                MeshFilter meshFilter = child.gameObject.GetComponent<MeshFilter>();
                if (meshFilter == null)
                {{
                    meshFilter = child.gameObject.AddComponent<MeshFilter>();
                }}

                // Allow the object to have physical contact with other objects
                MeshCollider meshCollider = child.gameObject.AddComponent<MeshCollider>();
                meshCollider.convex = false;
                meshCollider.sharedMesh = meshFilter.sharedMesh;

                // Assign a default material if missing
                if (meshRenderer.material == null)
                {{
                    meshRenderer.material = new Material(Shader.Find("Standard"));
                }}
            }}

            // Add collider and levelloader to exit portal

            string[] exitPortals = new string[] {exit_portals};
            int[] destinations = {destinations};
            string[] exitNames = {exit_names};

            if (exitPortals.Length == 0 || destinations.Length == 0 || exitNames.Length == 0)
            {{
                return instance;
            }}

            for (int i = 0; i < exitPortals.Length; i++)
            {{
                string portal = exitPortals[i];
                string exitName = exitNames[i];

                if (instance.name == portal)
                {{
                    BoxCollider bc = instance.GetComponent<BoxCollider>();
                    if (bc == null) bc = instance.AddComponent<BoxCollider>();
                    bc.isTrigger = true;

                    Rigidbody rb = instance.GetComponent<Rigidbody>();
                    if (rb == null) rb = instance.AddComponent<Rigidbody>();
                    rb.isKinematic = true;
                    rb.useGravity = false;

                    int destIdx = destinations[i];
                    string loaderName = $"LevelLoader_{{exitName}}_{scene_idx}_{{destIdx}}";
                    var loaderType = System.Type.GetType(loaderName);

                    if (loaderType != null)
                    {{
                        instance.AddComponent(loaderType);
                        Debug.Log($"Added {{loaderName}} to portal {{portal}}");
                    }}
                    else
                    {{
                        Debug.LogError($"Level loader type not found: {{loaderName}}");
                    }}
                }}
            }}

            // Load texture maps and apply them to the object
            ApplyTextures(instance, $"{{objDir}}/albedo.jpg", $"{{objDir}}/emission.jpg", $"{{objDir}}/normal.jpg");

            Logger_{scene_idx}.Log($"Object {{name}} loaded from {{objDir}} to {{position}} (rotation = {{rotation}}, scale = {{scale}})");
            return instance;
        }}
        else
        {{
            Logger_{scene_idx}.Log($"Failed to load {{objDir}}");
            return null;
        }}
    }}

    private static void LoadObject(string dirname, string name, Vector3 position = default, Vector3 rotation = default, Vector3 scale = default)
    {{
#nullable enable
        GameObject? objInstance = LoadAnyObject(dirname, name, position, rotation, scale);
#nullable disable
        if (objInstance != null)
        {{
            normalObjects.Add(objInstance);
            var rb = objInstance.GetComponent<Rigidbody>();
            if (rb != null) UnityEngine.Object.DestroyImmediate(rb);


            foreach (var mc in objInstance.GetComponentsInChildren<MeshCollider>())
            {{
                mc.convex = false;
                mc.isTrigger = false;
            }}

        }}
    }}

    private static void LoadConnection(string dirname, string name, Vector3 position = default, Vector3 rotation = default, Vector3 scale = default)
    {{
#nullable enable
        GameObject? objInstance = LoadAnyObject(dirname, name, position, rotation, scale);
#nullable disable
        if (objInstance != null)
        {{
            connections.Add(objInstance);
        }}
    }}

    private static void LoadRoom(string dirname, string name, Vector3 position = default, Vector3 rotation = default, Vector3 scale = default)
    {{
#nullable enable
        GameObject? objInstance = LoadAnyObject(dirname, name, position, rotation, scale);
#nullable disable
        if (objInstance != null)
        {{
            if (name.Contains("-floor"))
            {{
                floors.Add(objInstance);
            }}
            else if (name.Contains("-non_floor"))
            {{
                nonfloors.Add(objInstance);
            }}
            else if (name.Contains("-wall"))
            {{
                walls.Add(objInstance);
            }}
            var rb = objInstance.GetComponent<Rigidbody>();
            if (rb != null)
            {{
                UnityEngine.Object.DestroyImmediate(rb);
            }}
            foreach (var mc in objInstance.GetComponentsInChildren<MeshCollider>())
            {{
                mc.isTrigger = false;
                mc.convex = false;
            }}

        }}
    }}

    private static Light AddPointLight(string name, Vector3 position = default, float range = 10f, float intensity = 1f)
    {{
        Logger_{scene_idx}.Log($"AddPointLight({{position}})");

        Light pointLight = new GameObject(name).AddComponent<Light>();
        pointLight.type = LightType.Point;
        pointLight.transform.position = position;
        pointLight.range = range;
        pointLight.intensity = intensity;
        pointLight.shadows = LightShadows.Soft;
        pointLight.shadowStrength = 1f;
        pointLight.shadowBias = 0f;
        normalObjects.Add(pointLight.gameObject);
        return pointLight;
    }}

    private static void BuildExecutable()
    {{
        Logger_{scene_idx}.Log("BuildExecutable()");

        string[] scenes = {{ "Assets/Scenes/MainScene_{scene_idx}.unity" }};
        string buildPath;
        BuildTarget buildTarget;

        // Determine OS
        if (Application.platform == RuntimePlatform.OSXEditor)
        {{
            buildPath = "Builds/{package_name}-unity.app";
            buildTarget = BuildTarget.StandaloneOSX;
        }}
        else if (Application.platform == RuntimePlatform.WindowsEditor)
        {{
            buildPath = "Builds/{package_name}-unity.exe";
            buildTarget = Environment.Is64BitOperatingSystem ? BuildTarget.StandaloneWindows64 : BuildTarget.StandaloneWindows;
        }}
        else if (Application.platform == RuntimePlatform.LinuxEditor)
        {{
            buildPath = "Builds/{package_name}-unity.x86_64";
            buildTarget = BuildTarget.StandaloneLinux64;
        }}
        else
        {{
            Logger_{scene_idx}.Log($"Unsupported platform {{Application.platform}} for automatic build");
            return;
        }}

        BuildPlayerOptions buildPlayerOptions = new BuildPlayerOptions
        {{
            scenes = scenes,
            locationPathName = buildPath,
            target = buildTarget,
            options = BuildOptions.None
        }};
        BuildSummary summary = BuildPipeline.BuildPlayer(buildPlayerOptions).summary;
        Logger_{scene_idx}.Log(summary.result == BuildResult.Succeeded ? $"Executable built: {{buildPath}} ({{summary.totalSize}} bytes)" : "Failed to build executable");
    }}
}}

public class MultiAngleRenderer_{scene_idx}
{{
    public static void RenderScene_{scene_idx}(Camera camera, int resolutionX = 1024, int resolutionY = 1024, string dir = "Renders")
    {{
        camera.aspect = (float)resolutionX / (float)resolutionY;
        Bounds bounds = GetSceneBounds();
        if (bounds.size.Equals(Vector3.zero))
        {{
            Logger_{scene_idx}.Log("No renderable objects found in the scene. No rendering will be performed.");
            return;
        }}

        if (!Directory.Exists(dir))
        {{
            Directory.CreateDirectory(dir);
        }}

        float fixed_distance = bounds.size.magnitude;
        foreach (Vector3 rotation in GenerateRotations())
        {{
            camera.transform.eulerAngles = rotation;
            camera.transform.position = EulerToPosition(rotation.x, rotation.y, bounds.center, fixed_distance);
            string screenshotPath = $"{{dir}}/render_{{(int)rotation.x:D3}}-{{(int)rotation.y:D3}}-{{(int)rotation.z:D3}}.png";
            CaptureScreenshot(camera, screenshotPath, resolutionX, resolutionY);
        }}
    }}

    private static Bounds GetSceneBounds()
    {{
        MeshRenderer[] renderers = UnityEngine.Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None);
        if (renderers.Length == 0)
        {{
            return new Bounds(Vector3.zero, Vector3.zero);
        }}
        Bounds bounds = new Bounds(renderers[0].bounds.center, Vector3.zero);
        foreach (Renderer renderer in renderers)
        {{
            bounds.Encapsulate(renderer.bounds);
        }}
        return bounds;
    }}

    private static Vector3[] GenerateRotations()
    {{
        List<Vector3> rotations = new List<Vector3>();
        float[] pitches = {{ 0f, 30f, 45f, 60f, 90f }};
        float[] yaws = Enumerable.Range(0, 24).Select(i => i * 15f).ToArray();
        foreach (float pitch in pitches)
        {{
            foreach (float yaw in yaws)
            {{
                rotations.Add(new Vector3(pitch, yaw, 0));
            }}
        }}
        return rotations.ToArray();
    }}

    private static Vector3[] GetBBoxCorners(Bounds bounds)
    {{
        Vector3[] corners = {{
            new Vector3(bounds.min.x, bounds.min.y, bounds.min.z),
            new Vector3(bounds.min.x, bounds.min.y, bounds.max.z),
            new Vector3(bounds.min.x, bounds.max.y, bounds.min.z),
            new Vector3(bounds.min.x, bounds.max.y, bounds.max.z),
            new Vector3(bounds.max.x, bounds.min.y, bounds.min.z),
            new Vector3(bounds.max.x, bounds.min.y, bounds.max.z),
            new Vector3(bounds.max.x, bounds.max.y, bounds.min.z),
            new Vector3(bounds.max.x, bounds.max.y, bounds.max.z),
        }};
        return corners;
    }}

    private static Vector3 EulerToPosition(float pitch, float yaw, Vector3 center = default, float distance = 1)
    {{
        pitch *= Mathf.Deg2Rad;
        yaw *= Mathf.Deg2Rad;
        float x = -distance * Mathf.Cos(pitch) * Mathf.Sin(yaw);
        float y = distance * Mathf.Sin(pitch);
        float z = -distance * Mathf.Cos(pitch) * Mathf.Cos(yaw);
        return (new Vector3(x, y, z)) + center;
    }}

    private static void CaptureScreenshot(Camera camera, string path, int resolutionX = 1024, int resolutionY = 1024)
    {{
        RenderTexture renderTexture = new RenderTexture(resolutionX, resolutionY, 24);
        camera.targetTexture = renderTexture;

        // Render the scene
        camera.Render();

        // Create texture and read data
        RenderTexture.active = renderTexture;
        Texture2D screenshot = new Texture2D(renderTexture.width, renderTexture.height, TextureFormat.RGB24, false);
        screenshot.ReadPixels(new Rect(0, 0, renderTexture.width, renderTexture.height), 0, 0);
        screenshot.Apply();

        // Encode texture to PNG
        byte[] bytes = screenshot.EncodeToPNG();
        File.WriteAllBytes(path, bytes);

        // Cleanup
        camera.targetTexture = null;
        RenderTexture.active = null;
        UnityEngine.Object.DestroyImmediate(renderTexture);
        UnityEngine.Object.DestroyImmediate(screenshot);
    }}
}}
#endif
"""

CAMERA_CONTROLLER_TEMPLATE = """using UnityEngine;

public class CameraController_{scene_idx} : MonoBehaviour
{{
    public float moveSpeed = {move_speed}f;
    public float mouseSensitivity = {mouse_sensitivity}f;
    public float zoomSensitivity = 10f;
    public float minZoom = 15f;
    public float maxZoom = 60f;
    public bool hideCursor = true;

    private float yaw, pitch;
    private Camera cam;
    private CharacterController controller;

    void Start()
    {{
        cam = Camera.main;
        yaw = transform.eulerAngles.y;
        pitch = transform.eulerAngles.x;
        
        controller = GetComponent<CharacterController>();
        if (controller == null)
        {{
            controller = gameObject.AddComponent<CharacterController>();
            controller.height = 1.7f;
            controller.radius = 0.3f;
            controller.center = new Vector3(0f, 0.85f, 0f);
            controller.skinWidth = 0.05f;
            controller.minMoveDistance = 0.001f;
        }}
    }}

    void Update()
    {{
        if (cam != null)
        {{
            HandleMovement();
            HandleLook();
            HandleZoom();
        }}
        HideCursor();
    }}

    private void HandleMovement()
    {{
        float vertical = Input.GetAxisRaw("Vertical") * moveSpeed;
        float horizontal = Input.GetAxisRaw("Horizontal") * moveSpeed;
        float up = 0f;
        bool space = Input.GetKey(KeyCode.Space);
        bool shift = Input.GetKey(KeyCode.LeftShift);
        if ((space || shift) && !(space && shift))
        {{
            up = Mathf.Pow(-1, shift ? 1 : 0) * moveSpeed;
        }}
        Vector3 forward = Vector3.Normalize(new Vector3(transform.forward.x, 0, transform.forward.z));
        Vector3 right = Vector3.Normalize(new Vector3(transform.right.x, 0, transform.right.z));
        Vector3 move = (forward * vertical) + (right * horizontal) + (Vector3.up * up);
        controller.Move(move * Time.deltaTime);

    }}

    private void HandleLook()
    {{
        float mouseX = Input.GetAxisRaw("Mouse X") * mouseSensitivity;
        float mouseY = Input.GetAxisRaw("Mouse Y") * mouseSensitivity;
        yaw = (yaw + mouseX) % 360f;
        pitch = Mathf.Clamp(pitch - mouseY, -89f, 89f);
        transform.eulerAngles = new Vector3(pitch, yaw, 0f);
    }}

    private void HandleZoom()
    {{
        float scroll = Input.GetAxisRaw("Mouse ScrollWheel") * zoomSensitivity;
        if (scroll != 0f)
        {{
            cam.fieldOfView = Mathf.Clamp(cam.fieldOfView - scroll, minZoom, maxZoom);
        }}
    }}

    private void HideCursor()
    {{
        Cursor.lockState = hideCursor ? CursorLockMode.Locked : CursorLockMode.None;
    }}
}}
"""

KEYBOARD_TEMPLATE = """#if UNITY_EDITOR
using UnityEditor;
#endif
using UnityEngine;
using System.IO;

public class Keyboard_{scene_idx} : MonoBehaviour
{{
    void Update()
    {{
        if (Input.GetKeyDown(KeyCode.Escape))
        {{
#if UNITY_EDITOR
            EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }}
        if (Input.GetKeyDown(KeyCode.F2))
        {{
            TakeScreenshot();
        }}
    }}

    void TakeScreenshot()
    {{
        string screenshotDir = System.Environment.GetFolderPath(System.Environment.SpecialFolder.MyPictures);
        string timestamp = System.DateTime.Now.ToString("yyyyMMdd-HHmmss");
        string screenshotPath = Path.Combine(screenshotDir, $"{package_name}_screenshot_{{timestamp}}.png");
        ScreenCapture.CaptureScreenshot(screenshotPath);
    }}
}}
"""

OVERLAY_TEMPLATE = """#if UNITY_EDITOR
using UnityEditor;
#endif
using UnityEngine;

public class Overlay_{scene_idx} : MonoBehaviour
{{
    public float crosshairLength = 20f;
    public float raycastDistance = 10f;

    private Camera mainCamera;
    private float deltaTime = 0.0f;
    private bool showInfo = false;
    private string pointedObjectName = "";

    void Start()
    {{
        mainCamera = Camera.main;
    }}

    void Update()
    {{
        deltaTime += (Time.deltaTime - deltaTime) * 0.1f;
        if (Input.GetKeyDown(KeyCode.F3))
        {{
            showInfo = !showInfo;
        }}
        if (showInfo)
        {{
            UpdatePointedObjectName();
        }}
        else
        {{
            pointedObjectName = "";
        }}
    }}

    void OnGUI()
    {{
        if (showInfo)
        {{
            // Draw crosshair
            float xCenter = Screen.width / 2;
            float yCenter = Screen.height / 2;
            GUI.DrawTexture(new Rect(xCenter - crosshairLength / 2, yCenter - 1, crosshairLength, 2), Texture2D.whiteTexture); // Horizontal line
            GUI.DrawTexture(new Rect(xCenter - 1, yCenter - crosshairLength / 2, 2, crosshairLength), Texture2D.whiteTexture); // Vertical line

            // Initialize text style
            GUIStyle style = new GUIStyle
            {{
                fontSize = Mathf.CeilToInt(Screen.height * 0.02f),
                normal = new GUIStyleState {{ textColor = Color.white }}
            }};

            // FPS
            string fpsText = $"FPS: {{1.0f / deltaTime:0.}}";
            Vector2 fpsSize = style.CalcSize(new GUIContent(fpsText));

            // Camera position
            Vector3 cameraPosition = mainCamera.transform.position;
            string positionText = $"Position: {{cameraPosition.x:F2}} / {{cameraPosition.y:F2}} / {{cameraPosition.z:F2}}";
            Vector2 positionSize = style.CalcSize(new GUIContent(positionText));

            // Camera direction
            Vector3 cameraForward = mainCamera.transform.forward;
            string forwardText = $"Direction: {{cameraForward.x:F2}} / {{cameraForward.y:F2}} / {{cameraForward.z:F2}}";
            Vector2 forwardSize = style.CalcSize(new GUIContent(forwardText));

            // Object pointed at
            string objectNameText = $"Pointing at: {{pointedObjectName}}";
            Vector2 objectNameSize = style.CalcSize(new GUIContent(objectNameText));

            // Set background color
            GUI.color = new Color(0.2f, 0.2f, 0.2f, 0.8f);

            // Draw background box for each line
            GUI.Box(new Rect(10, 10, fpsSize.x + 10, fpsSize.y + 5), GUIContent.none);
            GUI.Box(new Rect(10, 10 + fpsSize.y + 5, positionSize.x + 10, positionSize.y + 5), GUIContent.none);
            GUI.Box(new Rect(10, 10 + fpsSize.y + positionSize.y + 10, forwardSize.x + 10, forwardSize.y + 5), GUIContent.none);
            GUI.Box(new Rect(10, 10 + fpsSize.y + positionSize.y + forwardSize.y + 15, objectNameSize.x + 10, objectNameSize.y + 5), GUIContent.none);

            // Set text color
            GUI.color = Color.white;

            // Display information
            GUI.Label(new Rect(15, 10, fpsSize.x, fpsSize.y), fpsText, style);
            GUI.Label(new Rect(15, 10 + fpsSize.y + 5, positionSize.x, positionSize.y), positionText, style);
            GUI.Label(new Rect(15, 10 + fpsSize.y + positionSize.y + 10, forwardSize.x, forwardSize.y), forwardText, style);
            GUI.Label(new Rect(15, 10 + fpsSize.y + positionSize.y + forwardSize.y + 15, objectNameSize.x, objectNameSize.y), objectNameText, style);

            // Top-right key commands display
            GUIStyle keyStyle = new GUIStyle
            {{
                fontSize = Mathf.CeilToInt(Screen.height * 0.02f),
                normal = new GUIStyleState {{ textColor = Color.white }}
            }};

            string[] keyCommands = new string[]
            {{
                "O - Toggle objects",
                "C - Toggle connections",
                "G - Toggle floor",
                "I - Toggle walls",
                "T - Toggle ceiling-less walls",
                "B - Toggle bounding boxes",
                "Right click - Toggle AR mode",
                "Left click - Place object (in AR mode)",
                "F2 - Screenshot",
                "F3 - Toggle overlay",
                "ESC - Quit"
            }};

            float maxWidth = 0f;
            float lineHeight = 0f;
            foreach (string command in keyCommands)
            {{
                Vector2 size = keyStyle.CalcSize(new GUIContent(command));
                if (size.x > maxWidth)
                {{
                    maxWidth = size.x;
                }}
                lineHeight = size.y;
            }}

            float padding = 5f;
            float spacing = 3f;
            float boxWidth = maxWidth + padding * 2;
            float boxHeight = keyCommands.Length * lineHeight + (keyCommands.Length - 1) * spacing + padding * 2;
            float xPos = Screen.width - boxWidth - 10f;
            float yPos = 10f;

            GUI.color = new Color(0.2f, 0.2f, 0.2f, 0.8f);
            GUI.Box(new Rect(xPos, yPos, boxWidth, boxHeight), GUIContent.none);
            GUI.color = Color.white;
            for (int i = 0; i < keyCommands.Length; i++)
            {{
                GUI.Label(new Rect(xPos + padding, yPos + padding + i * (lineHeight + spacing), maxWidth, lineHeight), keyCommands[i], keyStyle);
            }}
        }}
    }}

    private void UpdatePointedObjectName()
    {{
        Ray ray = mainCamera.ScreenPointToRay(new Vector3(Screen.width / 2, Screen.height / 2, 0));
        RaycastHit hit;
        if (Physics.Raycast(ray, out hit, raycastDistance))
        {{
            pointedObjectName = hit.collider.gameObject.transform.parent.gameObject.name;
        }}
        else
        {{
            pointedObjectName = "";
        }}
    }}
}}
"""

BOUNDING_BOX_DRAWER_TEMPLATE = """using UnityEngine;

public class BoundingBoxDrawer_{scene_idx} : MonoBehaviour
{{
    // Toggle flag to show/hide bounding boxes
    private bool showBoundingBoxes = false;

    // Material used for drawing lines
    private Material lineMaterial;

    // Line color and width settings
    public Color lineColor = Color.green;
    public float lineWidth = 1f; // Note: GL lines have fixed width on many platforms

    void Start()
    {{
        // Create a material with Unity's built-in "Hidden/Internal-Colored" shader.
        // This shader is available at runtime in builds as well.
        if (lineMaterial == null)
        {{
            Shader shader = Shader.Find("Hidden/Internal-Colored");
            if (shader == null)
            {{
                Debug.LogWarning("Could not find Hidden/Internal-Colored shader. Please ensure it is included in the build.");
                return;
            }}
            lineMaterial = new Material(shader)
            {{
                hideFlags = HideFlags.HideAndDontSave
            }};

            // Setup material blending etc.
            lineMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            lineMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            lineMaterial.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
            lineMaterial.SetInt("_ZWrite", 0);
        }}
    }}

    void Update()
    {{
        // Toggle bounding box drawing when B is pressed.
        if (Input.GetKeyDown(KeyCode.B))
        {{
            showBoundingBoxes = !showBoundingBoxes;
            Debug.Log("Bounding boxes toggled: " + showBoundingBoxes);
        }}
    }}

    // Draw the bounding boxes using GL calls.
    // OnRenderObject is called after camera rendering.
    void OnRenderObject()
    {{
        if (!showBoundingBoxes || lineMaterial == null)
            return;

        // Set the current material
        lineMaterial.SetPass(0);

        // Use GL to draw lines in world space
        GL.PushMatrix();
        // Using identity here causes vertices to be interpreted in world space
        GL.MultMatrix(Matrix4x4.identity);
        GL.Begin(GL.LINES);
        GL.Color(lineColor);

        // Find all MeshFilter components in the scene.
        MeshFilter[] meshFilters = FindObjectsByType<MeshFilter>(FindObjectsSortMode.None);
        foreach (MeshFilter mf in meshFilters)
        {{
            // Skip if there is no mesh.
            if (mf.sharedMesh == null)
                continue;

            // Get local bounds from the mesh.
            Bounds bounds = mf.sharedMesh.bounds;
            Vector3 center = bounds.center;
            Vector3 extents = bounds.extents;

            // Compute the eight corners of the bounding box in local space.
            Vector3[] localCorners = new Vector3[8];
            localCorners[0] = center + new Vector3(-extents.x, -extents.y, -extents.z);
            localCorners[1] = center + new Vector3(-extents.x, -extents.y,  extents.z);
            localCorners[2] = center + new Vector3(-extents.x,  extents.y, -extents.z);
            localCorners[3] = center + new Vector3(-extents.x,  extents.y,  extents.z);
            localCorners[4] = center + new Vector3( extents.x, -extents.y, -extents.z);
            localCorners[5] = center + new Vector3( extents.x, -extents.y,  extents.z);
            localCorners[6] = center + new Vector3( extents.x,  extents.y, -extents.z);
            localCorners[7] = center + new Vector3( extents.x,  extents.y,  extents.z);

            // Transform the local corners into world space using the object's transform.
            Vector3[] worldCorners = new Vector3[8];
            for (int i = 0; i < 8; i++)
            {{
                worldCorners[i] = mf.transform.TransformPoint(localCorners[i]);
            }}

            // Now draw 12 edges of the bounding box:
            // Bottom face edges: (0-1), (1-5), (5-4), (4-0)
            DrawGLLine(worldCorners[0], worldCorners[1]);
            DrawGLLine(worldCorners[1], worldCorners[5]);
            DrawGLLine(worldCorners[5], worldCorners[4]);
            DrawGLLine(worldCorners[4], worldCorners[0]);

            // Top face edges: (2-3), (3-7), (7-6), (6-2)
            DrawGLLine(worldCorners[2], worldCorners[3]);
            DrawGLLine(worldCorners[3], worldCorners[7]);
            DrawGLLine(worldCorners[7], worldCorners[6]);
            DrawGLLine(worldCorners[6], worldCorners[2]);

            // Vertical edges: (0-2), (1-3), (4-6), (5-7)
            DrawGLLine(worldCorners[0], worldCorners[2]);
            DrawGLLine(worldCorners[1], worldCorners[3]);
            DrawGLLine(worldCorners[4], worldCorners[6]);
            DrawGLLine(worldCorners[5], worldCorners[7]);
        }}

        GL.End();
        GL.PopMatrix();
    }}

    // Helper function to draw a line using GL
    private void DrawGLLine(Vector3 start, Vector3 end)
    {{
        GL.Vertex(start);
        GL.Vertex(end);
    }}
}}
"""

AR_DEMO_TEMPLATE = """using UnityEngine;
using UnityEngine.Rendering;

public class ARDemo_{scene_idx} : MonoBehaviour
{{
    // Optionally assign a prefab via the Inspector.
    // If left unassigned, a default multi-colored cube (with pivot at bottom) will be used.
    public GameObject objectToPlace;

    // Scale factor for the default cube.
    public float defaultCubeScale = 0.2f;

    // Flag to track whether AR mode is enabled.
    private bool arModeEnabled = false;

    // The AR indicator is now a transparent version of the object-to-be-placed.
    private GameObject indicator;

    // A container to hold placed objects (so we can easily remove them when AR mode is turned off).
    private GameObject placedObjectsContainer;

    // A hidden template prefab that is used for placement.
    private GameObject objectPrefab;

    void Start()
    {{
        // Create a container for the placed objects.
        placedObjectsContainer = new GameObject("PlacedARObjects");

        // If no object was assigned via Inspector, create our default colored cube.
        if (objectToPlace == null)
        {{
            objectPrefab = CreateColoredCube();
            objectPrefab.transform.localScale = Vector3.one * defaultCubeScale;
            objectPrefab.SetActive(false);
        }}
        else
        {{
            objectPrefab = objectToPlace;
            // Make sure the original object remains hidden.
            objectPrefab.SetActive(false);
        }}

        // Create the transparent indicator as a clone of our template.
        indicator = Instantiate(objectPrefab);
        indicator.name = "ARIndicator";
        indicator.SetActive(true);
        // Reset its transform scale so that it matches the template size (no pulsing).
        indicator.transform.localScale = objectPrefab.transform.localScale;
        // Make the indicator appear transparent.
        MakeTransparent(indicator, 0.5f);
    }}

    void Update()
    {{
        // Right-click toggles AR mode.
        if (Input.GetMouseButtonDown(1))
        {{
            arModeEnabled = !arModeEnabled;
            Debug.Log("AR Mode " + (arModeEnabled ? "Enabled" : "Disabled"));

            if (!arModeEnabled)
            {{
                // When disabled, clear all placed objects.
                ClearPlacedObjects();
            }}
        }}

        // Update the indicator if AR mode is enabled.
        if (arModeEnabled)
        {{
            Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
            RaycastHit hit;
            if (Physics.Raycast(ray, out hit))
            {{
                indicator.SetActive(true);
                // Place the indicator on the detected surface (with a slight offset to avoid z-fighting).
                indicator.transform.position = hit.point + hit.normal * 0.01f;
                // Rotate the indicator so its local up faces the detected surface normal.
                indicator.transform.rotation = Quaternion.FromToRotation(Vector3.up, hit.normal);
                // The indicator's scale remains constant.
            }}
            else
            {{
                indicator.SetActive(false);
            }}
        }}
        else
        {{
            indicator.SetActive(false);
        }}

        // When AR mode is enabled, left-click places a new copy of the object.
        if (arModeEnabled && Input.GetMouseButtonDown(0))
        {{
            Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
            RaycastHit hit;
            if (Physics.Raycast(ray, out hit))
            {{
                // Determine rotation so that the placed object's local up aligns with the surface normal.
                Quaternion placementRotation = Quaternion.FromToRotation(Vector3.up, hit.normal);
                Vector3 placementPosition;

                // For the default (cube with pivot at bottom) we place it flush with the surface.
                // For a custom object (assumed to be centered), offset by half its height.
                if (objectToPlace == null)
                {{
                    placementPosition = hit.point + hit.normal * 0.01f;
                }}
                else
                {{
                    Renderer rend = objectPrefab.GetComponentInChildren<Renderer>();
                    float height = (rend != null) ? rend.bounds.size.y : 1f;
                    placementPosition = hit.point + hit.normal * (height * 0.5f);
                }}

                // Create a new copy of our object prefab.
                GameObject placedObject = Instantiate(objectPrefab, placementPosition, placementRotation, placedObjectsContainer.transform);
                placedObject.name = objectPrefab.name + " Instance";
                placedObject.SetActive(true);
                Debug.Log("Placed object at: " + placementPosition);
            }}
            else
            {{
                Debug.Log("No surface detected at the clicked position.");
            }}
        }}
    }}

    // Sets all materials on the given GameObject to a transparent version.
    private void MakeTransparent(GameObject obj, float alpha)
    {{
        // Get all renderer components in the object.
        Renderer[] renderers = obj.GetComponentsInChildren<Renderer>();
        foreach (Renderer rend in renderers)
        {{
            Material[] mats = rend.materials;
            for (int i = 0; i < mats.Length; i++)
            {{
                // Create an instance so that we do not modify the original material.
                Material transparentMat = new Material(mats[i]);
                SetMaterialTransparent(transparentMat, alpha);
                mats[i] = transparentMat;
            }}
            rend.materials = mats;
        }}
    }}

    // Configures a material for transparency.
    private void SetMaterialTransparent(Material mat, float alpha)
    {{
        Color col = mat.color;
        col.a = alpha;
        mat.color = col;

        // Switch the shader to Fade mode (for transparency) by setting _Mode.
        mat.SetFloat("_Mode", 2);

        // Set up the material for transparency.
        mat.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.DisableKeyword("ALPHATEST_ON");
        mat.EnableKeyword("ALPHABLEND_ON");
        mat.DisableKeyword("ALPHAPREMULTIPLY_ON");
        mat.renderQueue = 3000;
    }}

    // Destroys all placed objects.
    private void ClearPlacedObjects()
    {{
        for (int i = placedObjectsContainer.transform.childCount - 1; i >= 0; i--)
        {{
            Destroy(placedObjectsContainer.transform.GetChild(i).gameObject);
        }}
    }}

    // Creates a multi-colored cube with 6 faces (each face gets its own material).
    // The cube is built with 24 vertices (4 per face) so that each face can have its own material.
    // All vertices are shifted upward by 0.5 so that the cube's pivot is at its bottom.
    private GameObject CreateColoredCube()
    {{
        GameObject cube = new GameObject("ColoredCube", typeof(MeshFilter), typeof(MeshRenderer));
        Mesh mesh = new Mesh();
        mesh.name = "ColoredCubeMesh";

        Vector3[] vertices = new Vector3[24];

        // Front face
        vertices[0] = new Vector3(-0.5f, -0.5f, 0.5f);
        vertices[1] = new Vector3(0.5f, -0.5f, 0.5f);
        vertices[2] = new Vector3(0.5f, 0.5f, 0.5f);
        vertices[3] = new Vector3(-0.5f, 0.5f, 0.5f);
        // Back face
        vertices[4] = new Vector3(0.5f, -0.5f, -0.5f);
        vertices[5] = new Vector3(-0.5f, -0.5f, -0.5f);
        vertices[6] = new Vector3(-0.5f, 0.5f, -0.5f);
        vertices[7] = new Vector3(0.5f, 0.5f, -0.5f);
        // Left face
        vertices[8] = new Vector3(-0.5f, -0.5f, -0.5f);
        vertices[9] = new Vector3(-0.5f, -0.5f, 0.5f);
        vertices[10] = new Vector3(-0.5f, 0.5f, 0.5f);
        vertices[11] = new Vector3(-0.5f, 0.5f, -0.5f);
        // Right face
        vertices[12] = new Vector3(0.5f, -0.5f, 0.5f);
        vertices[13] = new Vector3(0.5f, -0.5f, -0.5f);
        vertices[14] = new Vector3(0.5f, 0.5f, -0.5f);
        vertices[15] = new Vector3(0.5f, 0.5f, 0.5f);
        // Top face
        vertices[16] = new Vector3(-0.5f, 0.5f, 0.5f);
        vertices[17] = new Vector3(0.5f, 0.5f, 0.5f);
        vertices[18] = new Vector3(0.5f, 0.5f, -0.5f);
        vertices[19] = new Vector3(-0.5f, 0.5f, -0.5f);
        // Bottom face
        vertices[20] = new Vector3(-0.5f, -0.5f, -0.5f);
        vertices[21] = new Vector3(0.5f, -0.5f, -0.5f);
        vertices[22] = new Vector3(0.5f, -0.5f, 0.5f);
        vertices[23] = new Vector3(-0.5f, -0.5f, 0.5f);

        // Shift vertices upward by 0.5 so that the pivot is at the bottom.
        for (int i = 0; i < vertices.Length; i++)
        {{
            vertices[i] += Vector3.up * 0.5f;
        }}
        mesh.vertices = vertices;

        // Create 6 submeshes (one per face) with correct winding order.
        mesh.subMeshCount = 6;
        int[] frontTriangles = new int[] {{ 0, 1, 2, 0, 2, 3 }};
        int[] backTriangles = new int[] {{ 4, 5, 6, 4, 6, 7 }};
        int[] leftTriangles = new int[] {{ 8, 9, 10, 8, 10, 11 }};
        int[] rightTriangles = new int[] {{ 12, 13, 14, 12, 14, 15 }};
        int[] topTriangles = new int[] {{ 16, 17, 18, 16, 18, 19 }};
        int[] bottomTriangles = new int[] {{ 20, 21, 22, 20, 22, 23 }};
        mesh.SetTriangles(frontTriangles, 0);
        mesh.SetTriangles(backTriangles, 1);
        mesh.SetTriangles(leftTriangles, 2);
        mesh.SetTriangles(rightTriangles, 3);
        mesh.SetTriangles(topTriangles, 4);
        mesh.SetTriangles(bottomTriangles, 5);

        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        cube.GetComponent<MeshFilter>().mesh = mesh;

        // Create materials for each face.
        Material matFront = new Material(Shader.Find("Standard")); matFront.color = Color.red;
        Material matBack = new Material(Shader.Find("Standard")); matBack.color = Color.green;
        Material matLeft = new Material(Shader.Find("Standard")); matLeft.color = Color.blue;
        Material matRight = new Material(Shader.Find("Standard")); matRight.color = Color.yellow;
        Material matTop = new Material(Shader.Find("Standard")); matTop.color = Color.cyan;
        Material matBottom = new Material(Shader.Find("Standard")); matBottom.color = Color.magenta;
        cube.GetComponent<MeshRenderer>().materials = new Material[]
        {{
            matFront, matBack, matLeft, matRight, matTop, matBottom
        }};

        return cube;
    }}
}}
"""

TOGGLE_CONTROLLER_TEMPLATE = """using UnityEngine;

public class ToggleController_{scene_idx} : MonoBehaviour
{{
    public GameObject[] objectsToToggle;
    public KeyCode key;

    void Update()
    {{
        if (Input.GetKeyDown(key))
        {{
            Toggle();  
        }}
    }}

    public void Toggle()
    {{
        foreach (GameObject obj in objectsToToggle)
        {{
            obj.SetActive(!obj.activeSelf);
        }}
    }}
}}
"""

LEVEL_LOADER_TEMPLATE = """using UnityEngine;
using UnityEngine.SceneManagement;

public class LevelLoader_{name}_{scene_idx}_{dest_idx} : MonoBehaviour
{{
    private static float lastLoadTime;
    public float cooldownTime = 1.0f;

    [Header("Transition")]
    public float fadeOutDuration = 0.8f;
    public float fadeInDuration = 0.8f;

    [Header("Transition Effect")]
    public string effectType = "{effect_type}";

    private bool isLoading;

    private void Awake()
    {{
        lastLoadTime = Time.time;
    }}

    private void OnTriggerEnter(Collider other)
    {{  
        Debug.Log("LevelLoader_{name}_{scene_idx}_{dest_idx}: OnTriggerEnter by " + other.name);
        if (isLoading) return;

        // robust checks: tag OR has CharacterController
        bool isPlayer = other.CompareTag("MainCamera") ||
                        other.GetComponent<CharacterController>() != null ||
                        (other.attachedRigidbody == null && 
                        other.GetComponentInParent<CharacterController>() != null);

        if (!isPlayer) return;

        if (Time.time - lastLoadTime < cooldownTime) return;

        isLoading = true;
        lastLoadTime = Time.time;

        TransitionSystem.Instance.LoadSceneAuto(
            sceneName: "MainScene_{dest_idx}",
            effectType: effectType,
            fadeOutDuration: fadeOutDuration,
            fadeInDuration: fadeInDuration,
            additive: false
        );
    }}
}}
"""

TRANSITION_SYSTEM_TEMPLATE = """using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;

[DefaultExecutionOrder(-10000)]
public class TransitionSystem : MonoBehaviour
{{
    public static TransitionSystem Instance {{ get; private set; }}

    [Header("Fade")]
    public Color fadeColor = Color.black;
    public AnimationCurve fadeCurve = AnimationCurve.EaseInOut(0, 0, 1, 1);
    public bool autoFadeInOnStart = true;
    public float initialFadeInDuration = 0.6f;

    // Overlay textures
    private Texture2D overlayTex;    // solid 1x1
    private Texture2D circleTex;     // pre-baked solid circle (alpha 1 inside, 0 outside)

    // Generic fade
    private float alpha;
    private Coroutine fadeCo;
    private bool isTransitioning;
    public bool IsTransitioning => isTransitioning;
    public event System.Action OnTransitionStarted;
    public event System.Action OnTransitionFinished;

    // Iris wipe state (drawn in OnGUI)
    private bool irisActive;
    private float irisRadius;        // current radius (pixels)
    private float irisMaxRadius;     // target radius (pixels)
    private Color irisColor = Color.black;

    private void Awake()
    {{
        if (Instance != null)
        {{
            Destroy(gameObject);
            return;
        }}
        Instance = this;
        DontDestroyOnLoad(gameObject);
        BuildOverlay();
    }}

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void Bootstrap()
    {{
        if (Instance == null)
        {{
            var go = new GameObject("~TransitionSystem");
            go.hideFlags = HideFlags.DontSave;
            go.AddComponent<TransitionSystem>();
        }}
    }}

    private void Start()
    {{
        if (autoFadeInOnStart)
        {{
            alpha = 1f;
            StartCoroutine(FadeRoutine(0f, Mathf.Max(0.01f, initialFadeInDuration)));
        }}
    }}

    #region Overlay (no UnityEngine.UI required)
    private void BuildOverlay()
    {{
        // 1x1 overlay (for full-screen fade)
        overlayTex = new Texture2D(1, 1, TextureFormat.RGBA32, false);
        overlayTex.SetPixel(0, 0, Color.white);
        overlayTex.Apply();

        // Pre-baked circle texture for iris wipe (single creation)
        circleTex = GenerateCircleTexture(512); // Power-of-two; scalable during draw
        alpha = 0f;
    }}

    private Texture2D GenerateCircleTexture(int size)
    {{
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
        tex.wrapMode = TextureWrapMode.Clamp;

        float cx = (size - 1) * 0.5f;
        float cy = (size - 1) * 0.5f;
        float r = Mathf.Min(cx, cy);

        var pixels = new Color32[size * size];
        for (int y = 0; y < size; y++)
        {{
            for (int x = 0; x < size; x++)
            {{
                float dx = x - cx;
                float dy = y - cy;
                float dist = Mathf.Sqrt(dx * dx + dy * dy);
                byte a = (byte)(dist <= r ? 255 : 0);   // solid circle alpha
                pixels[y * size + x] = new Color32(255, 255, 255, a);
            }}
        }}
        tex.SetPixels32(pixels);
        tex.Apply(false, true);
        return tex;
    }}
    #endregion

    #region Public API
    // Auto load based on effectType parsed from scene_plan
    public void LoadSceneAuto(
        string sceneName,
        string effectType,
        float fadeOutDuration = 1f,
        float fadeInDuration = 1f,
        bool additive = false)
    {{
        if (string.IsNullOrEmpty(sceneName))
        {{
            Debug.LogError("TransitionSystem.LoadSceneAuto: sceneName is null or empty.");
            return;
        }}

        string eff = string.IsNullOrEmpty(effectType) ? "FadeInOut" : effectType;
        if (eff == "IrisWipe")
        {{
            StartCoroutine(LoadSceneWithIris(sceneName, fadeOutDuration, fadeInDuration, additive));
        }}
        else
        {{
            // Default to existing fade
            StartCoroutine(LoadSceneRoutine(sceneName, fadeOutDuration, fadeInDuration, additive));
        }}
    }}

    // Existing API remains
    public void LoadSceneWithFade(
        string sceneName,
        float fadeOutDuration = 1f,
        float fadeInDuration = 1f,
        bool additive = false)
    {{
        if (string.IsNullOrEmpty(sceneName))
        {{
            Debug.LogError("TransitionSystem.LoadSceneWithFade: sceneName is null or empty.");
            return;
        }}
        StartCoroutine(LoadSceneRoutine(sceneName, fadeOutDuration, fadeInDuration, additive));
    }}

    public Coroutine FadeOut(float duration) => StartCoroutine(FadeRoutine(1f, duration));
    public Coroutine FadeIn(float duration)  => StartCoroutine(FadeRoutine(0f, duration));
    public void SetFadeColor(Color color)    => fadeColor = color;
    #endregion

    #region Coroutines
    private IEnumerator LoadSceneRoutine(string sceneName, float fadeOutDuration, float fadeInDuration, bool additive)
    {{
        isTransitioning = true;
        OnTransitionStarted?.Invoke();

        // Fade to black
        yield return FadeRoutine(1f, fadeOutDuration);

        // Load scene
        AsyncOperation op = additive
            ? SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive)
            : SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Single);
        op.allowSceneActivation = true;
        while (!op.isDone) yield return null;
        yield return new WaitForEndOfFrame();

        // Fade in
        yield return FadeRoutine(0f, fadeInDuration);

        isTransitioning = false;
        OnTransitionFinished?.Invoke();
    }}

    // DRIVER ONLY: updates alpha; drawing happens in OnGUI
    private IEnumerator FadeRoutine(float targetAlpha, float duration)
    {{
        if (fadeCo != null) StopCoroutine(fadeCo);
        float startAlpha = alpha;
        float t = 0f;

        while (t < duration)
        {{
            t += Time.unscaledDeltaTime;
            float n = duration > 0f ? Mathf.Clamp01(t / duration) : 1f;
            float eased = fadeCurve.Evaluate(n);
            alpha = Mathf.Lerp(startAlpha, targetAlpha, eased);
            yield return null;
        }}
        alpha = targetAlpha;
    }}

    // NEW: Iris close -> load -> quick fade-in (IMGUI drawn in OnGUI)
    private IEnumerator LoadSceneWithIris(string sceneName, float closeDuration, float openFadeInDuration, bool additive)
    {{
        isTransitioning = true;
        OnTransitionStarted?.Invoke();

        // Compute max radius to cover screen diagonal (slightly overshoot)
        irisMaxRadius = Mathf.Sqrt(Screen.width * Screen.width + Screen.height * Screen.height) * 0.6f;
        irisRadius = 0f;
        irisActive = true;

        // Animate radius ONLY (no GUI calls here)
        float t = 0f;
        float dur = Mathf.Max(0.01f, closeDuration);
        while (t < dur)
        {{
            t += Time.unscaledDeltaTime;
            float k = Mathf.Clamp01(t / dur);
            irisRadius = Mathf.Lerp(0f, irisMaxRadius, k);
            yield return null;
        }}

        // Ensure fully closed
        irisRadius = irisMaxRadius;

        // Load next scene
        AsyncOperation op = additive
            ? SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive)
            : SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Single);
        op.allowSceneActivation = true;
        while (!op.isDone) yield return null;
        yield return new WaitForEndOfFrame();

        // Stop iris drawing, then quick fade-in using the standard overlay
        irisActive = false;
        alpha = 1f; // start from black
        yield return FadeRoutine(0f, Mathf.Min(openFadeInDuration, 0.6f));

        isTransitioning = false;
        OnTransitionFinished?.Invoke();
    }}
    #endregion

    #region OnGUI overlay (all GUI calls live here)
    private void OnGUI()
    {{
        // 1) Iris wipe (drawn first so fade overlay can sit above if needed)
        if (irisActive && circleTex != null)
        {{
            var prevC = GUI.color;
            GUI.color = irisColor;

            float size = irisRadius * 2f;
            float x = (Screen.width  * 0.5f) - irisRadius;
            float y = (Screen.height * 0.5f) - irisRadius;

            // Scales the pre-baked circle texture to current radius
            GUI.DrawTexture(new Rect(x, y, size, size), circleTex, ScaleMode.StretchToFill, true);
            GUI.color = prevC;
        }}

        // 2) Full-screen fade overlay
        if (alpha > 0f || isTransitioning)
        {{
            var prev = GUI.color;
            GUI.color = new Color(fadeColor.r, fadeColor.g, fadeColor.b, Mathf.Clamp01(alpha));
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), overlayTex);
            GUI.color = prev;
        }}
    }}
    #endregion
}}
"""