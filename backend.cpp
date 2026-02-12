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
    // We prefer the saved file (fileName) if provided, otherwise fall back to filePath.
    QString script = fileName.trimmed().isEmpty() ? filePath : fileName;

    // Accept either a local path (C:\...) or a file URL (file:///C:/...).
    if (script.startsWith("file:", Qt::CaseInsensitive)) {
        script = QUrl(script).toLocalFile();
    }

    // Nothing to run.
    if (script.isEmpty())
        return;

    const QFileInfo info(script);
    const QString workDir = info.absolutePath();
    const QString scriptQuoted = QString("\"%1\"").arg(QDir::toNativeSeparators(info.absoluteFilePath()));
    const QString workDirQuoted = QString("\"%1\"").arg(QDir::toNativeSeparators(workDir));

#if defined(Q_OS_WIN)
    // Build a PowerShell command that:
    // 1) cd's to the script directory
    // 2) runs python (or py as a fallback)
    const QString ps = QString(
        "Set-Location -LiteralPath %1; "
        "$py = (Get-Command python -ErrorAction SilentlyContinue); "
        "if ($py) { python %2 } else { py %2 }"
    ).arg(workDirQuoted, scriptQuoted);

    const QString wt = QStandardPaths::findExecutable("wt.exe");
    if (!wt.isEmpty()) {
        // Windows Terminal
        QProcess::startDetached(wt, {"powershell.exe", "-NoExit", "-Command", ps});
    } else {
        // Fallback to PowerShell console
        QProcess::startDetached("powershell.exe", {"-NoExit", "-Command", ps});
    }
#else
    // Non-Windows: run detached (no terminal). If you want a terminal, wire up gnome-terminal/xterm here.
    QProcess::startDetached("python3", {info.absoluteFilePath()}, workDir);
#endif
}

void Backend::fileUrlChanged()
{
    emited_state = true;


}
