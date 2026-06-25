package com.aion.chat;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

/** 启动页：输入服务器地址 */
public class LauncherActivity extends AppCompatActivity {

    private static final String PREFS = "aion_prefs";
    private static final String KEY_URL = "server_url";

    // 默认地址（首次打开时显示）
    private static final String DEFAULT_URL = "http://127.0.0.1:8080";

    private TextView tvStatus;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_launcher);

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        tvStatus = findViewById(R.id.tv_status);

        String savedUrl = prefs.getString(KEY_URL, DEFAULT_URL);

        Button btnLaunch = findViewById(R.id.btn_launch);
        btnLaunch.setOnClickListener(v -> {
            // 启动 Python 服务
            Intent serviceIntent = new Intent(this, PythonService.class);
            startService(serviceIntent);

            // 跳转 WebView
            Intent webViewIntent = new Intent(this, WebViewActivity.class);
            webViewIntent.putExtra("server_url", savedUrl);
            startActivity(webViewIntent);
            finish();
        });

        // 显示当前保存的地址
        tvStatus.setText("服务器地址：" + savedUrl);

        Button btnSettings = findViewById(R.id.btn_settings);
        btnSettings.setOnClickListener(v -> {
            // 简单弹窗设置地址（实际可做成单独页面）
            showUrlDialog();
        });
    }

    private void showUrlDialog() {
        android.app.AlertDialog.Builder builder = new android.app.AlertDialog.Builder(this);
        builder.setTitle("设置服务器地址");
        final android.widget.EditText input = new android.widget.EditText(this);
        input.setText(prefs.getString(KEY_URL, DEFAULT_URL));
        builder.setView(input);
        builder.setPositiveButton("保存", (dialog, which) -> {
            String url = input.getText().toString().trim();
            prefs.edit().putString(KEY_URL, url).apply();
            tvStatus.setText("服务器地址：" + url);
        });
        builder.setNegativeButton("取消", null);
        builder.show();
    }
}
