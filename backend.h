#ifndef BACKEND_H
#define BACKEND_H

#include <QObject>
#include <QCoreApplication>
#include <QDir>
#include <QDebug>
#include <QProcess>
#include <QFileDialog>
#include <QFileInfo>
#include <QUrl>
#include <QStandardPaths>
#include <QProcessEnvironment>

class Backend : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString path READ path WRITE setPath NOTIFY pathChanged)
    Q_PROPERTY(QString data READ data WRITE setData NOTIFY dataChanged)
    Q_PROPERTY(QString aiModel READ aiModel WRITE setAiModel NOTIFY aiModelChanged)
public:
    explicit Backend(QObject *parent = nullptr);


    void setEmittedState();



    QString path();
    void setPath(QString value);
    QString data();
    void setData(QString value);
    QString aiModel() const;
    void setAiModel(const QString &value);

    Q_INVOKABLE void runInTerminal(const QString &filePath, const QString &fileName);
    Q_INVOKABLE void uploadTemplateDirectory(const QString &directoryPath);
    Q_INVOKABLE QString defaultAiModel() const;
signals:
    void pathChanged();
    void dataChanged();
    void aiModelChanged();
    void templateUploadFinished(bool success, const QString &message);
    


//public Q_SLOTS:
public slots:
    void fileUrlChanged();
    bool getEmittedState();





private:
    bool copyDirectoryRecursively(const QString &sourcePath, const QString &destinationPath, QString *errorMessage) const;
    QString resolveTemplatesDirectory() const;
    QString nextAvailableDirectoryPath(const QString &directoryPath) const;
    QString normalizeAiModel(const QString &value) const;
    QString aiSettingsFilePath() const;
    bool saveAiSettingsToDisk(const QString &modelValue) const;
    QString loadAiSettingsFromDisk() const;

    QString m_path;
    bool emited_state;
    QString m_aiModel;
};

#endif // BACKEND_H
