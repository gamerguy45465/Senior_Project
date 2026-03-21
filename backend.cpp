#include "backend.h"

Backend::Backend(QObject *parent)
    : QObject{parent}
{
    m_path = QCoreApplication::applicationDirPath();
    m_path.append("/file.py");
    emited_state = false;


}

bool Backend::getEmittedState()
{
    return emited_state;

}

void Backend::setEmittedState()
{
    emited_state = false;

}

QString Backend::path()
{
    return m_path;

}

void Backend::setPath(QString value)
{
    m_path = value;
    m_path.remove("file://");
    emit pathChanged();

}

QString Backend::data()
{
    QFile file(m_path);
    if(!file.open(QIODevice::ReadOnly)) {
        qWarning() << "Error: File could not be read";
        return "";
    }

    QTextStream stream(&file);
    QString value = stream.readAll();
    file.close();
    return value;


}

void Backend::setData(QString value)
{
    QFile file(m_path);
    if(!file.open(QIODevice::WriteOnly)) {
        qWarning() << "could not write file!";
    }

    QTextStream stream(&file);
    stream << value;
    stream.flush();
    file.close();

}


void Backend::runInTerminal(const QString& filePath, const QString& fileName)
{
    auto toLocalPath = [](QString value) -> QString {
        value = value.trimmed();
        if (value.isEmpty())
            return QString();

        const QUrl url(value);
        if (url.isValid() && url.scheme().compare("file", Qt::CaseInsensitive) == 0)
            return url.toLocalFile();

        return QDir::fromNativeSeparators(value);
    };

    // Prefer filePath because QML passes documenthandler.fileUrl there.
    QString script = toLocalPath(filePath);

    // Fallback for callers that pass an absolute file path or file URL in fileName.
    if (script.isEmpty()) {
        const QString fallback = toLocalPath(fileName);
        if (!fallback.isEmpty())
            script = fallback;
    }

    if (script.isEmpty()) {
        qWarning() << "Run skipped: no script path provided.";
        return;
    }

    const QFileInfo info(script);
    if (!info.exists() || !info.isFile()) {
        qWarning() << "Run failed: script does not exist:" << script;
        return;
    }

    const QString workDir = info.absolutePath();
#if defined(Q_OS_WIN)
    const QString scriptNative = QDir::toNativeSeparators(info.absoluteFilePath());
    const QString workDirNative = QDir::toNativeSeparators(workDir);

    QString pyExecutable = QStandardPaths::findExecutable("py");
    if (pyExecutable.isEmpty())
        pyExecutable = QStandardPaths::findExecutable("python");

    if (pyExecutable.isEmpty()) {
        qWarning() << "Run failed: neither 'py' nor 'python' was found in PATH.";
        return;
    }

    const QString pyExecutableNative = QDir::toNativeSeparators(pyExecutable);
    auto psQuote = [](QString value) -> QString {
        return value.replace('\'', "''");
    };

    // Build a PowerShell command and pass it as EncodedCommand to avoid
    // quoting issues when routing through cmd.exe start.
    const QString psCommand = QString("Set-Location -LiteralPath '%1'; & '%2' '%3'; Write-Host ''; Write-Host ('Exit code: ' + $LASTEXITCODE)")
                                  .arg(psQuote(workDirNative),
                                       psQuote(pyExecutableNative),
                                       psQuote(scriptNative));
    qInfo() << "Run launching script:" << scriptNative << "with launcher:" << pyExecutableNative;
    const QByteArray psUtf16(reinterpret_cast<const char *>(psCommand.utf16()),
                             psCommand.size() * static_cast<int>(sizeof(ushort)));
    const QString encodedPsCommand = QString::fromLatin1(psUtf16.toBase64());

    // Force creation of a separate terminal window (instead of reusing IDE console).
    const QStringList launchArgs = {
        "/C",
        "start",
        "Python Script",
        "powershell.exe",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encodedPsCommand
    };

    if (!QProcess::startDetached("cmd.exe", launchArgs, workDir)) {
        qWarning() << "Run failed: could not start terminal window.";
    }
#else
    // Non-Windows: run detached (no terminal). If you want a terminal, wire up gnome-terminal/xterm here.
    if (!QProcess::startDetached("python3", {info.absoluteFilePath()}, workDir)) {
        qWarning() << "Run failed: could not start python3";
    }
#endif
}

void Backend::fileUrlChanged()
{
    emited_state = true;


}





