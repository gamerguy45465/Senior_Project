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


void Backend::runInTerminal(const QString& filePath, const QString& fileName) {
    // Ensure python is in PATH or use an absolute path to python.exe
    QString command = "python";
    QStringList args = {
        "-NoExit", "-Command", QString("cd /d \"%1\"; %2 \"%3\"").arg(QFileInfo(filePath).absolutePath(), command, filePath)
    };

    QProcess::startDetached("wt.exe", {"powershell.exe", args.join(" ")});

}

void Backend::fileUrlChanged()
{
    emited_state = true;


}
