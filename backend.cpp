#include "backend.h"

#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStringList>
#include <QTextStream>

namespace {

QString toLocalPath(QString value)
{
    value = value.trimmed();
    if (value.isEmpty())
        return QString();

    const QUrl url(value);
    if (url.isValid() && url.scheme().compare("file", Qt::CaseInsensitive) == 0)
        return url.toLocalFile();

    return QDir::fromNativeSeparators(value);
}

QString resolveScriptPath(const QString &filePath, const QString &fileName)
{
    // Prefer filePath because QML passes documenthandler.fileUrl there.
    QString scriptPath = toLocalPath(filePath);

    // Fallback for callers that pass an absolute file path or file URL in fileName.
    if (scriptPath.isEmpty()) {
        const QString fallbackPath = toLocalPath(fileName);
        if (!fallbackPath.isEmpty())
            scriptPath = fallbackPath;
    }

    return scriptPath;
}

QString findScriptFromStartDirectory(const QString &startPath,
                                     const QString &relativeScriptPath,
                                     int maxParentLevels = 8)
{
    if (startPath.trimmed().isEmpty())
        return QString();

    QDir directory(QDir::cleanPath(startPath));
    if (!directory.exists())
        return QString();

    for (int level = 0; level <= maxParentLevels; ++level) {
        const QFileInfo directCandidate(QDir(directory.absolutePath()).filePath(relativeScriptPath));
        if (directCandidate.exists() && directCandidate.isFile()) {
            return directCandidate.absoluteFilePath();
        }

        // Also check one directory level below each ancestor. This handles
        // common IDE layouts like .../Desktop/build-*/... with source in
        // .../Desktop/texteditor/.
        const QFileInfoList childDirectories = directory.entryInfoList(
            QDir::Dirs | QDir::NoDotAndDotDot);
        for (const QFileInfo &childInfo : childDirectories) {
            const QFileInfo childCandidate(QDir(childInfo.absoluteFilePath()).filePath(relativeScriptPath));
            if (childCandidate.exists() && childCandidate.isFile()) {
                return childCandidate.absoluteFilePath();
            }
        }

        if (!directory.cdUp())
            break;
    }

    return QString();
}

QString findScriptInDirectoryList(const QStringList &directories, const QString &relativeScriptPath)
{
    for (const QString &directoryPath : directories) {
        const QString candidate = findScriptFromStartDirectory(directoryPath, relativeScriptPath);
        if (!candidate.isEmpty())
            return candidate;
    }

    return QString();
}

QString resolveProjectScriptPath(const QString &relativeScriptPath)
{
    QStringList searchDirectories;

    auto appendDirectoryAndParents = [&searchDirectories](const QString &startPath) {
        if (startPath.trimmed().isEmpty())
            return;

        QDir directory(QDir::cleanPath(startPath));
        if (!directory.exists())
            return;

        searchDirectories << directory.absolutePath();
        for (int level = 0; level < 6; ++level) {
            if (!directory.cdUp())
                break;
            searchDirectories << directory.absolutePath();
        }
    };

#ifdef TEXTEDITOR_SOURCE_DIR
    appendDirectoryAndParents(QString::fromUtf8(TEXTEDITOR_SOURCE_DIR));
#endif
    appendDirectoryAndParents(QCoreApplication::applicationDirPath());
    appendDirectoryAndParents(QDir::currentPath());
    searchDirectories.removeDuplicates();

    return findScriptInDirectoryList(searchDirectories, relativeScriptPath);
}

void launchPythonScript(const QString &scriptPath, bool debugMode)
{
    const QString modeLabel = debugMode ? "Debug" : "Run";
    const QFileInfo scriptInfo(scriptPath);
    if (!scriptInfo.exists() || !scriptInfo.isFile()) {
        qWarning() << modeLabel << "failed: script does not exist:" << scriptPath;
        return;
    }

    const QString workDir = scriptInfo.absolutePath();
#if defined(Q_OS_WIN)
    const QString scriptNative = QDir::toNativeSeparators(scriptInfo.absoluteFilePath());
    const QString workDirNative = QDir::toNativeSeparators(workDir);

    QString pyExecutable = QStandardPaths::findExecutable("py");
    QStringList interpreterArgs;
    if (!pyExecutable.isEmpty()) {
        // Force Python 3 when using the Windows launcher.
        interpreterArgs << "-3";
    } else {
        pyExecutable = QStandardPaths::findExecutable("python");
    }
    if (pyExecutable.isEmpty())
        pyExecutable = QStandardPaths::findExecutable("python3");

    if (pyExecutable.isEmpty()) {
        qWarning() << modeLabel << "failed: no Python launcher/interpreter was found in PATH.";
        return;
    }

    const QString pyExecutableNative = QDir::toNativeSeparators(pyExecutable);
    auto psQuote = [](QString value) -> QString {
        return value.replace('\'', "''");
    };

    QStringList scriptArgs = interpreterArgs;
    if (debugMode) {
        scriptArgs << "-m" << "pdb";
    }
    scriptArgs << scriptNative;

    QStringList quotedScriptArgs;
    quotedScriptArgs.reserve(scriptArgs.size());
    for (const QString &arg : scriptArgs) {
        quotedScriptArgs << QString("'%1'").arg(psQuote(arg));
    }

    const QString pythonInvocation = QString("& '%1' %2")
                                         .arg(psQuote(pyExecutableNative),
                                              quotedScriptArgs.join(' '));

    // Build a PowerShell command and pass it as EncodedCommand to avoid
    // quoting issues when routing through cmd.exe start.
    const QString psCommand = QString("Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue; "
                                      "Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue; "
                                      "Set-Location -LiteralPath '%1'; %2; Write-Host ''; Write-Host ('Exit code: ' + $LASTEXITCODE)")
                                  .arg(psQuote(workDirNative),
                                       pythonInvocation);
    qInfo() << modeLabel << "launching script:" << scriptNative << "with launcher:" << pyExecutableNative;

    const QByteArray psUtf16(reinterpret_cast<const char *>(psCommand.utf16()),
                             psCommand.size() * static_cast<int>(sizeof(ushort)));
    const QString encodedPsCommand = QString::fromLatin1(psUtf16.toBase64());

    const QString terminalTitle = debugMode ? "Python Debugger" : "Python Script";
    const QStringList launchArgs = {
        "/C",
        "start",
        terminalTitle,
        "powershell.exe",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encodedPsCommand
    };

    if (!QProcess::startDetached("cmd.exe", launchArgs, workDir)) {
        qWarning() << modeLabel << "failed: could not start terminal window.";
    }
#else
    QStringList pythonArgs;
    if (debugMode) {
        pythonArgs << "-m" << "pdb";
    }
    pythonArgs << scriptInfo.absoluteFilePath();

    if (!QProcess::startDetached("python3", pythonArgs, workDir)) {
        qWarning() << modeLabel << "failed: could not start python3.";
    }
#endif
}

} // namespace

Backend::Backend(QObject *parent)
    : QObject{parent}
{
    m_path = QCoreApplication::applicationDirPath();
    m_path.append("/file.py");
    emited_state = false;
    m_aiModel = loadAiSettingsFromDisk();


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

QString Backend::aiModel() const
{
    return m_aiModel;
}

void Backend::setAiModel(const QString &value)
{
    const QString normalized = normalizeAiModel(value);
    const bool changed = (normalized != m_aiModel);

    m_aiModel = normalized;
    if (!saveAiSettingsToDisk(m_aiModel)) {
        qWarning() << "Failed to save AI settings file:" << aiSettingsFilePath();
    }

    if (changed) {
        emit aiModelChanged();
    }
}

QString Backend::defaultAiModel() const
{
    return QStringLiteral("gpt-5.2");
}

QString Backend::normalizeAiModel(const QString &value) const
{
    const QString trimmed = value.trimmed();
    if (trimmed.isEmpty()) {
        return defaultAiModel();
    }

    return trimmed;
}

QString Backend::aiSettingsFilePath() const
{
    QString basePath = QStandardPaths::writableLocation(QStandardPaths::AppConfigLocation);
    if (basePath.isEmpty()) {
        basePath = QDir::home().filePath(".config/Text Editor");
    }

    return QDir(basePath).filePath("ai_settings.json");
}

bool Backend::saveAiSettingsToDisk(const QString &modelValue) const
{
    const QString settingsPath = aiSettingsFilePath();
    const QFileInfo info(settingsPath);
    QDir dir = info.dir();
    if (!dir.exists() && !dir.mkpath(".")) {
        return false;
    }

    QFile file(settingsPath);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        return false;
    }

    QJsonObject root;
    root.insert("model", modelValue);

    const QJsonDocument doc(root);
    const qint64 bytesWritten = file.write(doc.toJson(QJsonDocument::Indented));
    const bool flushed = file.flush();
    file.close();

    return bytesWritten >= 0 && flushed;
}

QString Backend::loadAiSettingsFromDisk() const
{
    const QString settingsPath = aiSettingsFilePath();
    QFile file(settingsPath);
    if (!file.exists()) {
        return defaultAiModel();
    }

    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qWarning() << "Unable to read AI settings file:" << settingsPath;
        return defaultAiModel();
    }

    const QByteArray raw = file.readAll();
    file.close();

    QJsonParseError error{};
    const QJsonDocument doc = QJsonDocument::fromJson(raw, &error);
    if (error.error != QJsonParseError::NoError || !doc.isObject()) {
        qWarning() << "AI settings file contains invalid JSON:" << settingsPath;
        return defaultAiModel();
    }

    const QString modelValue = doc.object().value("model").toString();
    return normalizeAiModel(modelValue);
}


void Backend::runInTerminal(const QString& filePath, const QString& fileName)
{
    const QString scriptPath = resolveScriptPath(filePath, fileName);
    if (scriptPath.isEmpty()) {
        qWarning() << "Run skipped: no script path provided.";
        return;
    }

    launchPythonScript(scriptPath, false);
}

void Backend::debugInTerminal(const QString &filePath, const QString &fileName)
{
    const QString scriptPath = resolveScriptPath(filePath, fileName);
    if (scriptPath.isEmpty()) {
        qWarning() << "Debug skipped: no script path provided.";
        return;
    }

    launchPythonScript(scriptPath, true);
}

void Backend::runAiGenerate(const QString &filePath, const QString &fileName)
{
    const QString sourceFilePath = resolveScriptPath(filePath, fileName);
    if (sourceFilePath.isEmpty()) {
        qWarning() << "AI Generate skipped: no active file path provided.";
        return;
    }

    const QFileInfo sourceInfo(sourceFilePath);
    if (!sourceInfo.exists() || !sourceInfo.isFile()) {
        qWarning() << "AI Generate skipped: active file is invalid:" << sourceFilePath;
        return;
    }

    const QString agentScriptPath = resolveProjectScriptPath(QStringLiteral("python/agent.py"));
    if (agentScriptPath.isEmpty()) {
        qWarning() << "AI Generate failed: unable to locate python/agent.py.";
        return;
    }

    qputenv("TEXTEDITOR_ACTIVE_FILE", QDir::toNativeSeparators(sourceInfo.absoluteFilePath()).toUtf8());
    launchPythonScript(agentScriptPath, false);
}

void Backend::uploadTemplateDirectory(const QString &directoryPath)
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

    const QString sourcePath = toLocalPath(directoryPath);
    const QFileInfo sourceInfo(sourcePath);

    if (sourcePath.isEmpty() || !sourceInfo.exists() || !sourceInfo.isDir()) {
        emit templateUploadFinished(false, "Please select a valid directory to upload.");
        return;
    }

    const QString templatesPath = resolveTemplatesDirectory();
    if (!QDir().mkpath(templatesPath)) {
        emit templateUploadFinished(false,
                                   QString("Unable to create or access Templates folder: %1")
                                       .arg(QDir::toNativeSeparators(templatesPath)));
        return;
    }

    const QString requestedDestination = QDir(templatesPath).filePath(sourceInfo.fileName());
    const QString finalDestination = nextAvailableDirectoryPath(requestedDestination);
    const QString cleanSourcePath = QDir::cleanPath(sourceInfo.absoluteFilePath());
    const QString cleanDestinationPath = QDir::cleanPath(finalDestination);

#if defined(Q_OS_WIN)
    const Qt::CaseSensitivity pathSensitivity = Qt::CaseInsensitive;
#else
    const Qt::CaseSensitivity pathSensitivity = Qt::CaseSensitive;
#endif

    const QString sourcePrefix = cleanSourcePath + QDir::separator();
    if (cleanDestinationPath.startsWith(sourcePrefix, pathSensitivity)) {
        emit templateUploadFinished(false,
                                    "Please select a source directory outside the Templates root.");
        return;
    }

    QString errorMessage;
    if (!copyDirectoryRecursively(sourceInfo.absoluteFilePath(), finalDestination, &errorMessage)) {
        QDir(finalDestination).removeRecursively();
        emit templateUploadFinished(false, errorMessage);
        return;
    }

    emit templateUploadFinished(true,
                                QString("Template directory copied to: %1")
                                    .arg(QDir::toNativeSeparators(finalDestination)));
}

void Backend::uploadTemplateDirectoryInteractive()
{
    QString initialDirectory = resolveTemplatesDirectory();
    if (initialDirectory.isEmpty() || !QDir(initialDirectory).exists()) {
        initialDirectory = QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation);
    }

    const QString selectedDirectory = QFileDialog::getExistingDirectory(
        nullptr,
        tr("Select Template Directory"),
        initialDirectory,
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks);

    if (selectedDirectory.isEmpty())
        return;

    uploadTemplateDirectory(selectedDirectory);
}

bool Backend::copyDirectoryRecursively(const QString &sourcePath,
                                       const QString &destinationPath,
                                       QString *errorMessage) const
{
    QDir sourceDir(sourcePath);
    if (!sourceDir.exists()) {
        if (errorMessage)
            *errorMessage = QString("Source directory does not exist: %1")
                                .arg(QDir::toNativeSeparators(sourcePath));
        return false;
    }

    if (!QDir().mkpath(destinationPath)) {
        if (errorMessage)
            *errorMessage = QString("Failed to create destination directory: %1")
                                .arg(QDir::toNativeSeparators(destinationPath));
        return false;
    }

    const QFileInfoList entries = sourceDir.entryInfoList(
        QDir::NoDotAndDotDot | QDir::NoSymLinks | QDir::Dirs | QDir::Files | QDir::Hidden | QDir::System);

    for (const QFileInfo &entry : entries) {
        const QString sourceItemPath = entry.absoluteFilePath();
        const QString destinationItemPath = QDir(destinationPath).filePath(entry.fileName());

        if (entry.isDir()) {
            if (!copyDirectoryRecursively(sourceItemPath, destinationItemPath, errorMessage))
                return false;
            continue;
        }

        if (entry.isFile()) {
            if (QFile::exists(destinationItemPath) && !QFile::remove(destinationItemPath)) {
                if (errorMessage)
                    *errorMessage = QString("Failed to overwrite file: %1")
                                        .arg(QDir::toNativeSeparators(destinationItemPath));
                return false;
            }

            if (!QFile::copy(sourceItemPath, destinationItemPath)) {
                if (errorMessage)
                    *errorMessage = QString("Failed to copy file: %1")
                                        .arg(QDir::toNativeSeparators(sourceItemPath));
                return false;
            }

            QFile::setPermissions(destinationItemPath, entry.permissions());
        }
    }

    return true;
}

QString Backend::resolveTemplatesDirectory() const
{
    auto stripBuildConfigDirectory = [](QDir directory) -> QDir {
        const QString directoryName = directory.dirName().toLower();
        if (directoryName == "debug"
            || directoryName == "release"
            || directoryName == "relwithdebinfo"
            || directoryName == "minsizerel") {
            directory.cdUp();
        }
        return directory;
    };

    auto isProjectRoot = [](const QDir &directory) -> bool {
        return QFileInfo::exists(directory.filePath("texteditor.pro"))
               || QFileInfo::exists(directory.filePath("CMakeLists.txt"));
    };

    auto findProjectRootFrom = [&](QDir startDirectory) -> QString {
        QDir candidate(startDirectory);
        while (candidate.exists()) {
            if (isProjectRoot(candidate))
                return candidate.absolutePath();

            const QFileInfoList childDirectories = candidate.entryInfoList(
                QDir::Dirs | QDir::NoDotAndDotDot);
            for (const QFileInfo &childInfo : childDirectories) {
                QDir childDir(childInfo.absoluteFilePath());
                if (!isProjectRoot(childDir))
                    continue;

                if (QDir(childDir.filePath("Templates")).exists())
                    return childDir.absolutePath();
            }

            if (!candidate.cdUp())
                break;
        }

        return QString();
    };

    QString appRootPath;
#ifdef TEXTEDITOR_SOURCE_DIR
    const QString compiledRootPath = QDir::cleanPath(QString::fromUtf8(TEXTEDITOR_SOURCE_DIR));
    if (!compiledRootPath.isEmpty() && QDir(compiledRootPath).exists()) {
        appRootPath = QDir(compiledRootPath).absolutePath();
    }
#endif

    if (appRootPath.isEmpty()) {
        appRootPath = findProjectRootFrom(QDir::currentPath());
    }

    if (appRootPath.isEmpty()) {
        const QDir executableDirectory = stripBuildConfigDirectory(QDir(QCoreApplication::applicationDirPath()));
        appRootPath = findProjectRootFrom(executableDirectory);
    }

    if (appRootPath.isEmpty()) {
        const QDir executableDirectory = stripBuildConfigDirectory(QDir(QCoreApplication::applicationDirPath()));
        appRootPath = executableDirectory.absolutePath();
    }

    return QDir(appRootPath).filePath("Templates");
}

QString Backend::nextAvailableDirectoryPath(const QString &directoryPath) const
{
    if (!QFileInfo::exists(directoryPath))
        return directoryPath;

    const QFileInfo info(directoryPath);
    const QDir parentDir = info.dir();
    const QString baseName = info.fileName();

    for (int index = 1; index < 10000; ++index) {
        const QString suffix = index == 1 ? "_copy" : QString("_copy_%1").arg(index);
        const QString candidatePath = parentDir.filePath(baseName + suffix);
        if (!QFileInfo::exists(candidatePath))
            return candidatePath;
    }

    return parentDir.filePath(baseName + "_copy_fallback");
}

void Backend::fileUrlChanged()
{
    emited_state = true;


}





