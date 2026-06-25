package com.aion.chat;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;

/**
 * 启动 Python 后端服务的前台 Service。
 * 从 assets/aion-chat/ 目录运行 Python，端口 8080。
 */
public class PythonService extends Service {

    private static final String TAG = "PythonService";
    private Process pythonProcess;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        new Thread(this::startPython).start();
        return START_STICKY;
    }

    private void copyAssetFile(String assetName, File destFile) throws Exception {
        if (destFile.exists()) return;
        InputStream in = getAssets().open(assetName);
        FileOutputStream out = new FileOutputStream(destFile);
        byte[] buf = new byte[8192];
        int len;
        while ((len = in.read(buf)) > 0) {
            out.write(buf, 0, len);
        }
        out.close();
        in.close();
        destFile.setExecutable(true, false);
        Log.i(TAG, "已提取: " + assetName + " -> " + destFile);
    }

    private void startPython() {
        try {
            File appDir = getFilesDir();
            File pythonDir = new File(appDir, "aion-chat");
            File pythonBin = new File(appDir, "python3.13");
            File mainScript = new File(pythonDir, "main.py");

            // 确保目录存在
            pythonDir.mkdirs();

            // 复制 Python 二进制（从 assets 根目录）
            try {
                copyAssetFile("python3.13", pythonBin);
            } catch (Exception e) {
                Log.w(TAG, "Python 二进制不在 assets 根目录，跳过: " + e.getMessage());
            }

            // 复制 aion-chat 目录（如果不存在）
            File assetChatDir = new File(getFilesDir(), "aion-chat-asset");
            if (!mainScript.exists()) {
                copyAssetDir("aion-chat", pythonDir);
            }

            // 检查 main.py 是否存在
            if (!mainScript.exists()) {
                Log.e(TAG, "main.py 不存在: " + mainScript);
                return;
            }

            // 构建命令
            String pythonExe = pythonBin.exists() ? pythonBin.getAbsolutePath() : "python3";
            ProcessBuilder pb = new ProcessBuilder(
                pythonExe, "-u", mainScript.getAbsolutePath()
            );
            pb.directory(pythonDir);
            pb.environment().put("PYTHONPATH", pythonDir.getAbsolutePath());
            pb.environment().put("PORT", "8080");
            pb.environment().put("HOME", appDir.getAbsolutePath());
            pb.redirectErrorStream(true);

            Log.i(TAG, "启动 Python: " + pythonExe + " " + mainScript.getAbsolutePath());
            pythonProcess = pb.start();

            BufferedReader reader = new BufferedReader(
                new InputStreamReader(pythonProcess.getInputStream()));
            String line;
            while ((line = reader.readLine()) != null) {
                Log.d(TAG, "[python] " + line);
            }

            int exitCode = pythonProcess.waitFor();
            Log.i(TAG, "Python 进程退出，代码: " + exitCode);

        } catch (Exception e) {
            Log.e(TAG, "Python 启动失败", e);
        }
    }

    private void copyAssetDir(String assetPath, File destDir) {
        try {
            String[] files = getAssets().list(assetPath);
            if (files == null || files.length == 0) return;
            destDir.mkdirs();
            for (String name : files) {
                String fullAssetPath = assetPath + "/" + name;
                File destFile = new File(destDir, name);
                InputStream in = getAssets().open(fullAssetPath);
                FileOutputStream out = new FileOutputStream(destFile);
                byte[] buf = new byte[8192];
                int len;
                while ((len = in.read(buf)) > 0) out.write(buf, 0, len);
                out.close();
                in.close();
                Log.i(TAG, "已提取: " + fullAssetPath);
            }
        } catch (Exception e) {
            Log.e(TAG, "复制 assets 失败: " + assetPath, e);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (pythonProcess != null) {
            pythonProcess.destroy();
        }
        super.onDestroy();
    }
}
